#!/usr/bin/env bash
# ===========================================================================
#  deploy.sh - despliegue de English Practice Hub
#
#  Flujo: git pull && ./deploy.sh
#
#  Flags:
#    --all     fuerza rebuild completo
#    --logs    sigue logs al terminar
# ===========================================================================
set -euo pipefail

cd "$(dirname "$0")"

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; C='\033[0;36m'; B='\033[1m'; N='\033[0m'
ok()   { echo -e "${G}✔${N} $*"; }
info() { echo -e "${C}›${N} $*"; }
warn() { echo -e "${Y}●${N} $*"; }
err()  { echo -e "${R}✖${N} $*" >&2; }

STATE_FILE=".deploy_state"
COMPOSE="docker compose"

command -v docker >/dev/null || { err "docker no instalado"; exit 1; }
$COMPOSE version >/dev/null 2>&1 || { err "'docker compose' no disponible"; exit 1; }
[ -f .env ] || { err "Falta .env (cp .env.example .env y editar)"; exit 1; }

if ! docker network inspect shared-net >/dev/null 2>&1; then
  warn "Red 'shared-net' no existe. Creandola..."
  docker network create shared-net >/dev/null
  ok "Red shared-net creada"
fi

FORCE_ALL=false
FOLLOW_LOGS=false
for arg in "$@"; do
  case "$arg" in
    --all)  FORCE_ALL=true ;;
    --logs) FOLLOW_LOGS=true ;;
    *) err "Flag desconocido: $arg"; exit 1 ;;
  esac
done

detect_changes() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    warn "No es repo git -> rebuild completo"
    FORCE_ALL=true; return
  fi

  local current
  current="$(git rev-parse HEAD)"

  if [ ! -f "$STATE_FILE" ]; then
    warn "Primer deploy -> rebuild completo"
    FORCE_ALL=true; return
  fi

  local last changed
  last="$(cat "$STATE_FILE")"
  changed="$( { git diff --name-only "$last" HEAD 2>/dev/null; git diff --name-only HEAD 2>/dev/null; } | sort -u )"

  if [ -z "$changed" ]; then
    info "Sin cambios desde el ultimo deploy."
    exit 0
  fi

  echo -e "${B}Archivos cambiados:${N}"
  echo "$changed" | sed 's/^/   /'
}

if ! $FORCE_ALL; then
  detect_changes
fi

info "Reconstruyendo..."
$COMPOSE up -d --build

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git rev-parse HEAD > "$STATE_FILE"
  ok "Estado guardado ($(cat "$STATE_FILE" | cut -c1-8))"
fi

echo ""
ok "Despliegue terminado."
$COMPOSE ps

if $FOLLOW_LOGS; then
  echo ""
  info "Logs (Ctrl+C para salir):"
  $COMPOSE logs -f app
fi
