#!/bin/sh
set -eu
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <backup.dump>" >&2
  exit 2
fi
BACKUP="$1"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.local.yml}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-english_db}"
REMOTE="/tmp/english_restore.dump"
[ -f "$BACKUP" ] || { echo "Backup not found: $BACKUP" >&2; exit 2; }
docker compose -f "$COMPOSE_FILE" stop backend >/dev/null
trap 'docker compose -f "$COMPOSE_FILE" start backend >/dev/null' EXIT
docker compose -f "$COMPOSE_FILE" cp "$BACKUP" "postgres:$REMOTE"
docker compose -f "$COMPOSE_FILE" exec -T postgres pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner "$REMOTE"
docker compose -f "$COMPOSE_FILE" exec -T postgres rm -f "$REMOTE" >/dev/null
echo "Restore completed."
