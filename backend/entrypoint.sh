#!/bin/bash
set -e

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Starting Gunicorn server ==="
exec gunicorn --bind 0.0.0.0:7860 --workers 1 --worker-class gthread --threads 2 --timeout 300 config.wsgi:application
