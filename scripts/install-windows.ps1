[CmdletBinding()]
param(
    [string]$Domain,
    [ValidateRange(1, 65535)]
    [int]$HttpPort,
    [string]$ProjectName,
    [switch]$BehindHttpsProxy,
    [switch]$NonInteractive,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"

function Read-TextSetting {
    param(
        [string]$Prompt,
        [string]$CurrentValue,
        [string]$DefaultValue
    )

    if ($NonInteractive -or -not [string]::IsNullOrWhiteSpace($CurrentValue)) {
        if ([string]::IsNullOrWhiteSpace($CurrentValue)) { return $DefaultValue }
        return $CurrentValue
    }

    $answer = Read-Host "$Prompt [$DefaultValue]"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultValue }
    return $answer.Trim()
}

function Read-PortSetting {
    param([int]$CurrentValue)

    if ($CurrentValue -gt 0) { return $CurrentValue }
    if ($NonInteractive) { return 8080 }

    while ($true) {
        $answer = Read-Host "Lokaler HTTP-Port [8080]"
        if ([string]::IsNullOrWhiteSpace($answer)) { return 8080 }
        $parsed = 0
        if ([int]::TryParse($answer, [ref]$parsed) -and $parsed -ge 1 -and $parsed -le 65535) {
            return $parsed
        }
        Write-Warning "Bitte einen Port zwischen 1 und 65535 eingeben."
    }
}

function New-HexSecret {
    param([int]$Bytes = 32)
    $buffer = New-Object byte[] $Bytes
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    } finally {
        $generator.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "'$Name' wurde nicht gefunden. Bitte Docker Desktop installieren und erneut starten."
    }
}

function Invoke-DockerBuild {
    foreach ($attempt in 1..3) {
        & docker compose --env-file $EnvPath build
        if ($LASTEXITCODE -eq 0) { return }
        if ($attempt -lt 3) {
            $delay = $attempt * 5
            Write-Warning "Docker-Build fehlgeschlagen (Versuch $attempt/3). Neuer Versuch in $delay Sekunden."
            Start-Sleep -Seconds $delay
        }
    }
    throw "Docker-Build ist nach drei Versuchen fehlgeschlagen."
}

function Start-DockerInfrastructure {
    foreach ($attempt in 1..3) {
        & docker compose --env-file $EnvPath up -d db redis
        if ($LASTEXITCODE -eq 0) { return }
        if ($attempt -lt 3) {
            $delay = $attempt * 5
            Write-Warning "PostgreSQL/Redis-Start fehlgeschlagen (Versuch $attempt/3). Neuer Versuch in $delay Sekunden."
            Start-Sleep -Seconds $delay
        }
    }
    throw "PostgreSQL/Redis konnten nach drei Versuchen nicht gestartet werden."
}

Push-Location $ProjectRoot
try {
    Write-Host ""
    Write-Host "basicERP - Einrichtung fuer Windows" -ForegroundColor Cyan
    Write-Host "Linux-Container werden ueber Docker Desktop gestartet." -ForegroundColor DarkGray
    Write-Host ""

    $reuseExistingEnv = (Test-Path -LiteralPath $EnvPath) -and -not $Force
    if ($reuseExistingEnv) {
        $existingSettings = @{}
        foreach ($line in Get-Content -LiteralPath $EnvPath) {
            if ($line -match "^[A-Za-z_][A-Za-z0-9_]*=") {
                $parts = $line.Split("=", 2)
                $existingSettings[$parts[0]] = $parts[1]
            }
        }
        foreach ($requiredKey in @("APP_DOMAIN", "APP_HTTP_PORT", "COMPOSE_PROJECT_NAME", "APP_PUBLIC_SCHEME")) {
            if (-not $existingSettings.ContainsKey($requiredKey)) {
                throw "Die bestehende .env ist unvollstaendig ($requiredKey fehlt). Mit -Force neu erzeugen."
            }
        }
        $Domain = $existingSettings["APP_DOMAIN"]
        $HttpPort = [int]$existingSettings["APP_HTTP_PORT"]
        $ProjectName = $existingSettings["COMPOSE_PROJECT_NAME"]
        $BehindHttpsProxy = $existingSettings["APP_PUBLIC_SCHEME"] -eq "https"
        Write-Host "Bestehende .env wird fuer die Wiederaufnahme verwendet." -ForegroundColor Yellow
    } else {
        $Domain = Read-TextSetting -Prompt "Domain oder Hostname (ohne Protokoll/Pfad)" -CurrentValue $Domain -DefaultValue "localhost"
        $HttpPort = Read-PortSetting -CurrentValue $HttpPort
        $ProjectName = Read-TextSetting -Prompt "Docker-Projektname" -CurrentValue $ProjectName -DefaultValue "basicerp"

        if (-not $NonInteractive -and -not $PSBoundParameters.ContainsKey("BehindHttpsProxy")) {
            $proxyAnswer = Read-Host "Wird basicERP hinter einem externen HTTPS-Reverse-Proxy betrieben? [j/N]"
            $BehindHttpsProxy = $proxyAnswer -match "^(j|ja|y|yes)$"
        }
    }

    if ($Domain -match "://|/|\s") {
        throw "Die Domain darf kein Protokoll, keinen Pfad und keine Leerzeichen enthalten. Beispiel: erp.example.de"
    }

    if ($ProjectName -notmatch "^[a-z0-9][a-z0-9_-]*$") {
        throw "Der Docker-Projektname darf nur Kleinbuchstaben, Zahlen, Unterstrich und Bindestrich enthalten."
    }

    Assert-Command -Name "docker"
    & docker compose version | Out-Null
    & docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop ist installiert, aber die Linux-Engine laeuft nicht. Docker Desktop starten und das Skript erneut ausfuehren."
    }

    $publicScheme = if ($BehindHttpsProxy) { "https" } else { "http" }
    if ($BehindHttpsProxy) {
        $publicOrigin = "https://$Domain"
    } elseif ($HttpPort -eq 80) {
        $publicOrigin = "http://$Domain"
    } else {
        $publicOrigin = "http://${Domain}:$HttpPort"
    }

    if (-not $reuseExistingEnv) {
        $allowedHosts = @($Domain, "localhost", "127.0.0.1") | Select-Object -Unique
        $dbPassword = New-HexSecret -Bytes 24
        $djangoSecret = New-HexSecret -Bytes 48
        $databaseUrl = "postgresql://basicerp:${dbPassword}@db:5432/basicerp"

        $envContent = @(
            "COMPOSE_PROJECT_NAME=$ProjectName"
            "APP_DOMAIN=$Domain"
            "APP_PUBLIC_SCHEME=$publicScheme"
            "APP_HTTP_PORT=$HttpPort"
            "APP_TIME_ZONE=Europe/Berlin"
            "DJANGO_SECRET_KEY=$djangoSecret"
            "DJANGO_DEBUG=false"
            "DJANGO_ALLOWED_HOSTS=$($allowedHosts -join ',')"
            "CSRF_TRUSTED_ORIGINS=$publicOrigin"
            "POSTGRES_DB=basicerp"
            "POSTGRES_USER=basicerp"
            "POSTGRES_PASSWORD=$dbPassword"
            "DATABASE_URL=$databaseUrl"
            "REDIS_URL=redis://redis:6379/0"
            ""
        ) -join "`n"
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($EnvPath, $envContent, $utf8NoBom)
        Write-Host ".env wurde mit zufaelligen Secrets angelegt." -ForegroundColor Green
    }

    & docker compose --env-file $EnvPath config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Die Compose-Konfiguration ist ungueltig." }

    Write-Host "Container-Images werden gebaut ..." -ForegroundColor Cyan
    Invoke-DockerBuild

    Start-DockerInfrastructure

    Write-Host "Datenbankmigrationen werden ausgefuehrt ..." -ForegroundColor Cyan
    & docker compose --env-file $EnvPath run --rm web python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "Datenbankmigration fehlgeschlagen." }

    $adminEmail = if ($Domain -eq "localhost") { "admin@localhost.invalid" } else { "admin@$Domain" }
    & docker compose --env-file $EnvPath run --rm `
        -e INITIAL_ADMIN_USERNAME=admin `
        -e INITIAL_ADMIN_PASSWORD=admin `
        -e "INITIAL_ADMIN_EMAIL=$adminEmail" `
        web python manage.py bootstrap_admin
    if ($LASTEXITCODE -ne 0) { throw "Der initiale Admin konnte nicht erstellt werden." }

    & docker compose --env-file $EnvPath up -d
    if ($LASTEXITCODE -ne 0) { throw "basicERP konnte nicht gestartet werden." }

    $localUrl = "http://localhost:$HttpPort"
    Write-Host "Warte auf den Healthcheck ..." -ForegroundColor Cyan
    $ready = $false
    foreach ($attempt in 1..30) {
        try {
            $response = Invoke-WebRequest -Uri "$localUrl/api/v1/health/ready/" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ready) {
        Write-Warning "Der Healthcheck ist noch nicht bereit. Diagnose: docker compose logs --tail 100"
    }

    Write-Host ""
    Write-Host "basicERP ist eingerichtet." -ForegroundColor Green
    Write-Host "Lokal:      $localUrl"
    Write-Host "Oeffentlich: $publicOrigin"
    Write-Host "Benutzer:   admin"
    Write-Host "Passwort:   admin"
    Write-Host ""
    Write-Warning "Das Installationspasswort ist oeffentlich bekannt. Die Anwendung erzwingt nach der ersten Anmeldung einen Passwortwechsel."
    if ($BehindHttpsProxy) {
        Write-Warning "HTTPS muss im externen Reverse Proxy auf localhost:$HttpPort weitergeleitet werden."
    }
    Write-Host ("Fahrplan/Testhilfe: {0}/roadmap/" -f $localUrl)
} finally {
    Pop-Location
}
