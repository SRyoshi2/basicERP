[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [string]$ProjectName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"

function Get-EnvValue {
    param([string]$Name)
    $line = Get-Content -LiteralPath $EnvPath | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (-not $line) { return "" }
    return $line.Split("=", 2)[1]
}

function Invoke-Compose {
    param([string[]]$ComposeArguments)
    & docker compose --env-file $EnvPath --project-name $ProjectName @ComposeArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose ist fehlgeschlagen: $($ComposeArguments -join ' ')" }
}

if (-not (Test-Path -LiteralPath $EnvPath)) { throw ".env fehlt. Bitte basicERP zuerst installieren." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker wurde nicht gefunden." }
if ([string]::IsNullOrWhiteSpace($ProjectName)) { $ProjectName = Get-EnvValue "COMPOSE_PROJECT_NAME" }
if ($ProjectName -notmatch "^[a-z0-9][a-z0-9_-]*$") { throw "Ungueltiger Docker-Projektname." }

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $ProjectRoot "backups\basicerp-$timestamp"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $OutputDirectory) { throw "Ziel existiert bereits: $OutputDirectory" }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null

$remotePrefix = "/tmp/basicerp-backup-$timestamp"
$servicesToRestart = @()
Push-Location $ProjectRoot
try {
    Invoke-Compose @("up", "-d", "--wait", "db")
    $runningServices = & docker compose --env-file $EnvPath --project-name $ProjectName ps --services --status running
    if ($LASTEXITCODE -ne 0) { throw "Laufende Dienste konnten nicht ermittelt werden." }
    $servicesToRestart = @("web", "worker", "nginx") | Where-Object { $runningServices -contains $_ }
    if ($servicesToRestart.Count -gt 0) {
        Invoke-Compose (@("stop") + $servicesToRestart)
    }
    Invoke-Compose @("exec", "-T", "db", "sh", "-c", "pg_dump -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" --format=custom --file=$remotePrefix.dump")
    Invoke-Compose @("cp", "db:$remotePrefix.dump", (Join-Path $OutputDirectory "database.dump"))

    Invoke-Compose @("run", "--rm", "--no-deps", "web", "sh", "-c", "tar -C /app/archive -czf /tmp/archive.tar.gz . && tar -C /app/media -czf /tmp/media.tar.gz . && cp /tmp/archive.tar.gz /tmp/media.tar.gz /app/media/")
    Invoke-Compose @("cp", "web:/app/media/archive.tar.gz", (Join-Path $OutputDirectory "archive.tar.gz"))
    Invoke-Compose @("cp", "web:/app/media/media.tar.gz", (Join-Path $OutputDirectory "media.tar.gz"))
    Invoke-Compose @("run", "--rm", "--no-deps", "web", "sh", "-c", "rm -f /app/media/archive.tar.gz /app/media/media.tar.gz")
    Invoke-Compose @("exec", "-T", "db", "rm", "-f", "$remotePrefix.dump")

    $files = @("database.dump", "archive.tar.gz", "media.tar.gz")
    $checksumLines = foreach ($file in $files) {
        $hash = (Get-FileHash -LiteralPath (Join-Path $OutputDirectory $file) -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $file"
    }
    [System.IO.File]::WriteAllLines((Join-Path $OutputDirectory "SHA256SUMS"), $checksumLines, [System.Text.UTF8Encoding]::new($false))

    $manifest = [ordered]@{
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        source_project = $ProjectName
        includes = @("PostgreSQL", "Archiv", "Medien")
        excludes = @(".env", "Redis-Warteschlange")
    } | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText((Join-Path $OutputDirectory "manifest.json"), $manifest, [System.Text.UTF8Encoding]::new($false))

    Write-Host "Backup erfolgreich: $OutputDirectory" -ForegroundColor Green
    Write-Warning "Die .env ist nicht enthalten und muss separat sicher verwahrt werden."
} catch {
    Write-Error $_
    throw
} finally {
    if ($servicesToRestart.Count -gt 0) {
        & docker compose --env-file $EnvPath --project-name $ProjectName up -d @servicesToRestart
    }
    Pop-Location
}
