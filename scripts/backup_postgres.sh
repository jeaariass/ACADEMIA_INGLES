#!/bin/sh
set -eu
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.local.yml}"
OUTPUT_DIR="${OUTPUT_DIR:-backups}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-english_db}"
STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="$OUTPUT_DIR/english_db_$STAMP.dump"
REMOTE="/tmp/english_db_$STAMP.dump"
mkdir -p "$OUTPUT_DIR"
docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -f "$REMOTE"
docker compose -f "$COMPOSE_FILE" cp "postgres:$REMOTE" "$TARGET"
docker compose -f "$COMPOSE_FILE" exec -T postgres rm -f "$REMOTE" >/dev/null
echo "Backup created: $TARGET"
