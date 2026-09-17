#!/bin/sh
set -e

if [ ! -f "migrations/env.py" ]; then
    echo "[startup] Initializing persistent migrations..."

    # Remove Git placeholder before Flask-Migrate initializes the directory
    rm -f migrations/.gitkeep

    flask db init
    flask db migrate -m "initial academic schema"
fi

echo "[startup] Applying database migrations..."
flask db upgrade

echo "[startup] Seeding initial users..."
python -c "
from app import create_app
from app.seed import seed_initial_data

app = create_app()
with app.app_context():
    seed_initial_data()

print('[startup] Initial users ready.')
"

echo "[startup] Starting gunicorn..."
exec gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app
