#!/bin/sh
set -e

# Primera vez: crea carpeta de migraciones si no existe
if [ ! -f "migrations/env.py" ]; then
    echo "[startup] Inicializando migraciones por primera vez..."
    flask db init
    flask db migrate -m "initial"
fi

echo "[startup] Aplicando migraciones..."
flask db upgrade

echo "[startup] Sembrando datos iniciales..."
python -c "
from app import create_app, db
from app.seed import seed_initial_data
app = create_app()
with app.app_context():
    seed_initial_data()
print('[startup] Seed completo.')
"

echo "[startup] Arrancando gunicorn..."
exec gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app
