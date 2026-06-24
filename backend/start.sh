#!/bin/sh
set -e
echo "[startup] Inicializando BD..."
python -c "from app import create_app; create_app(); print('[startup] BD lista.')"
echo "[startup] Arrancando gunicorn..."
exec gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app
