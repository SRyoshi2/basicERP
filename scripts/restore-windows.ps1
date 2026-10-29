[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [string]$ProjectName,
    [switch]$ConfirmRestore,
    [switch]$SkipSafetyBackup,
    [switch]$NoStart
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
$BackupDirectory = (Resolve-Path -LiteralPath $BackupDirectory).Path
$requiredFiles = @("database.dump", "archive.tar.gz", "media.tar.gz", "SHA256SUMS", "manifest.json")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $BackupDirectory $file) -PathType Leaf)) {
        throw "Backup ist unvollstaendig: $file fehlt."
    }
}

$checksumText = Get-Content -Raw -LiteralPath (Join-Path $BackupDirectory "SHA256SUMS")
foreach ($file in @("database.dump", "archive.tar.gz", "media.tar.gz")) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $BackupDirectory $file) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($checksumText -notmatch "(?m)^$actual  $([regex]::Escape($file))\r?$") {
        throw "Pruefsumme stimmt nicht: $file"
    }
}

if ([string]::IsNullOrWhiteSpace($ProjectName)) { $ProjectName = Get-EnvValue "COMPOSE_PROJECT_NAME" }
if ($ProjectName -notmatch "^[a-z0-9][a-z0-9_-]*$") { throw "Ungueltiger Docker-Projektname." }
$databaseName = Get-EnvValue "POSTGRES_DB"
$databaseUser = Get-EnvValue "POSTGRES_USER"
if ($databaseName -notmatch "^[A-Za-z_][A-Za-z0-9_]*$" -or $databaseUser -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    throw "Datenbankname oder -benutzer in .env ist ungueltig."
}

if (-not $ConfirmRestore) {
    $answer = Read-Host "RESTORE eingeben, um Projekt '$ProjectName' zu ueberschreiben"
    if ($answer -cne "RESTORE") { throw "Wiederherstellung abgebrochen." }
}

Push-Location $ProjectRoot
try {
    if (-not $SkipSafetyBackup) {
        $safetyPath = Join-Path $ProjectRoot ("backups\pre-restore-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        & (Join-Path $PSScriptRoot "backup-windows.ps1") -OutputDirectory $safetyPath -ProjectName $ProjectName
        if ($LASTEXITCODE -ne 0) { throw "Sicherheitsbackup vor Restore fehlgeschlagen." }
    }

    & docker compose --env-file $EnvPath --project-name $ProjectName stop web worker beat nginx 2>$null
    Invoke-Compose @("up", "-d", "--wait", "db")
    Invoke-Compose @("cp", (Join-Path $BackupDirectory "database.dump"), "db:/tmp/basicerp-restore.dump")
    $databaseCommand = "dropdb -U `"`$POSTGRES_USER`" --maintenance-db=postgres --if-exists `"`$POSTGRES_DB`" && createdb -U `"`$POSTGRES_USER`" -O `"`$POSTGRES_USER`" `"`$POSTGRES_DB`" && pg_restore -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" --no-owner /tmp/basicerp-restore.dump && rm -f /tmp/basicerp-restore.dump"
    Invoke-Compose @("exec", "-T", "db", "sh", "-c", $databaseCommand)

    $mount = "${BackupDirectory}:/restore:ro"
    $fileCommand = "find /app/archive -mindepth 1 -delete && find /app/media -mindepth 1 -delete && tar -C /app/archive -xzf /restore/archive.tar.gz && tar -C /app/media -xzf /restore/media.tar.gz"
    Invoke-Compose @("run", "--rm", "--no-deps", "--volume", $mount, "web", "sh", "-c", $fileCommand)
    Invoke-Compose @("run", "--rm", "web", "python", "manage.py", "migrate", "--noinput")
    Invoke-Compose @("run", "--rm", "web", "python", "manage.py", "check")

    if (-not $NoStart) {
        Invoke-Compose @("up", "-d")
    }
    Write-Host "Restore erfolgreich fuer Projekt '$ProjectName'." -ForegroundColor Green
} finally {
    Pop-Location
}
