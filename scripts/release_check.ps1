param([string]$ComposeFile = "docker-compose.local.yml")
$ErrorActionPreference = "Stop"
Write-Host "Building and starting the release candidate..."
docker compose -f $ComposeFile up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose startup failed." }

Write-Host "Waiting for readiness..."
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:8000/readyz" -TimeoutSec 3
        if ($r.ok) { break }
    } catch {}
    Start-Sleep -Seconds 2
}

$r = Invoke-RestMethod -Uri "http://localhost:8000/readyz" -TimeoutSec 5
if (-not $r.ok) { throw "Application is not ready." }

Write-Host "Running database/content integrity checks..."
docker compose -f $ComposeFile exec -T backend python qa/production_check.py
if ($LASTEXITCODE -ne 0) { throw "Production checks failed." }

Write-Host "Release checks passed."
