# Build y push de la imagen del backend a GHCR, para desplegar despues en el VPS.
#
# Uso:
#   docker login ghcr.io -u jeaariass          (una vez, token con write:packages)
#   .\scripts\build-and-push.ps1
#
# Luego en el VPS:
#   TAG=<commit7 impreso abajo> en /srv/stacks/academia/.env
#   /srv/scripts/portainer-stack.sh academia --pull
param(
    [string]$Tag
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not $Tag) {
    $Tag = (git rev-parse --short=7 HEAD).Trim()
}

$image = "ghcr.io/jeaariass/academia-api:$Tag"

Write-Host "Construyendo $image..."
docker build -t $image ./backend

Write-Host "Subiendo $image..."
docker push $image

Write-Host ""
Write-Host "Listo. En el VPS:"
Write-Host "  TAG=$Tag en /srv/stacks/academia/.env"
Write-Host "  /srv/scripts/portainer-stack.sh academia --pull"
