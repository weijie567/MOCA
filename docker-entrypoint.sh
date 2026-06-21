#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head
echo "Migrations complete. Starting server..."
exec "$@"
