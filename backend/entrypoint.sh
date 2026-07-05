#!/bin/bash
set -e

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Starting Gunicorn server ==="
exec gunicorn --bind 0.0.0.0:7860 --workers 2 --timeout 120 config.wsgi:application
