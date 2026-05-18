#!/usr/bin/env sh
set -eu

# Migrations are run by CI/CD before deploy. Startup runs only
# brand seeding, static files, and the app server.

PORT="${PORT:-8000}"

echo "🏷️  Ensuring default brand exists..."
python manage.py create_default_brand --skip-checks 2>/dev/null || true

echo "📤 Collecting static files..."
python manage.py collectstatic --noinput

# Ensure Prometheus multi-process directory is clean
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
  echo "🧹 Cleaning Prometheus multiproc directory: ${PROMETHEUS_MULTIPROC_DIR}..."
  mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
  # Remove all files from the directory (but not subdirectories)
  find "${PROMETHEUS_MULTIPROC_DIR}" -maxdepth 1 -type f -delete 2>/dev/null || true
fi

WORKERS="${GUNICORN_WORKERS:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
echo "🚀 Starting Gunicorn (workers=${WORKERS}, timeout=${TIMEOUT})..."
exec gunicorn store.wsgi:application --bind "0.0.0.0:${PORT}" --workers "${WORKERS}" --timeout "${TIMEOUT}"
