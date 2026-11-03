#!/usr/bin/env bash
set -e

# Wait for PostgreSQL to accept connections before starting Django.
if [ -n "$POSTGRES_HOST" ]; then
    echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
    until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex(('${POSTGRES_HOST}', int('${POSTGRES_PORT:-5432}'))))" 2>/dev/null; do
        sleep 1
    done
    echo "PostgreSQL is ready."
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-false}" = "true" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
