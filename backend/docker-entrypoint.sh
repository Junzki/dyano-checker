#!/bin/sh
set -e

if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

exec "$@"
