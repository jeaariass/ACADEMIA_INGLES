#!/bin/sh
set -eu

APP_ENV="${APP_ENV:-development}"

if [ ! -f "migrations/env.py" ]; then
    echo "[startup] ERROR: migrations/env.py is missing. Refusing to generate production migrations at runtime." >&2
    exit 1
fi

if [ "$APP_ENV" = "production" ]; then
    case "${FLASK_SECRET_KEY:-}" in
        ""|"change-this-secret"|"dev-secret-change-me"|"dev-local-secret-key")
            echo "[startup] ERROR: configure a strong FLASK_SECRET_KEY before production startup." >&2
            exit 1
            ;;
    esac
fi

echo "[startup] Applying database migrations..."
flask db upgrade

echo "[startup] Seeding safe initial data..."
python - <<'PY'
from app import create_app
from app.seed import seed_initial_data

app = create_app()
with app.app_context():
    seed_initial_data()
print("[startup] Seed complete.")
PY

if [ "${RUN_STARTUP_QA:-0}" = "1" ]; then
    echo "[startup] Running production checks..."
    python qa/production_check.py
fi

WORKERS="${GUNICORN_WORKERS:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"

echo "[startup] Starting gunicorn with ${WORKERS} worker(s)..."
exec gunicorn \
    --workers "$WORKERS" \
    --bind 0.0.0.0:8000 \
    --timeout "$TIMEOUT" \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    wsgi:app
