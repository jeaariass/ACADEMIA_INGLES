param(
    [Parameter(Mandatory=$true)][string]$BackupFile,
    [string]$ComposeFile = "docker-compose.local.yml",
    [string]$DbUser = "postgres",
    [string]$DbName = "english_db"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $BackupFile)) { throw "Backup file not found: $BackupFile" }
$remote = "/tmp/english_restore.dump"

Write-Host "Stopping backend before restore..."
docker compose -f $ComposeFile stop backend | Out-Null
try {
    docker compose -f $ComposeFile cp $BackupFile "postgres:$remote"
    if ($LASTEXITCODE -ne 0) { throw "Could not copy backup to PostgreSQL container." }

    Write-Host "Restoring database. Existing objects will be replaced..."
    docker compose -f $ComposeFile exec -T postgres pg_restore -U $DbUser -d $DbName --clean --if-exists --no-owner $remote
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed." }

    docker compose -f $ComposeFile exec -T postgres rm -f $remote | Out-Null
}
finally {
    Write-Host "Starting backend..."
    docker compose -f $ComposeFile start backend | Out-Null
}
Write-Host "Restore completed."
