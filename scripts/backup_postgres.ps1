param(
    [string]$ComposeFile = "docker-compose.local.yml",
    [string]$OutputDir = "backups",
    [string]$DbUser = "postgres",
    [string]$DbName = "english_db"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$target = Join-Path $OutputDir "english_db_$stamp.dump"
$remote = "/tmp/english_db_$stamp.dump"

Write-Host "Creating PostgreSQL backup..."
docker compose -f $ComposeFile exec -T postgres pg_dump -U $DbUser -d $DbName -Fc -f $remote
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed." }

docker compose -f $ComposeFile cp "postgres:$remote" $target
if ($LASTEXITCODE -ne 0) { throw "Could not copy backup from container." }

docker compose -f $ComposeFile exec -T postgres rm -f $remote | Out-Null
Write-Host "Backup created: $target"
