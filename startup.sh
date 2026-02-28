#!/usr/bin/env sh
set -eu

# Resilient startup: retry migrations on transient DB/pooler failures.
# If migrations still fail after retries, exit 1 (fail fast — do not start app).

MAX_RETRIES="${MIGRATE_MAX_RETRIES:-8}"
SLEEP_SECONDS="${MIGRATE_RETRY_SLEEP_SECONDS:-10}"
RUN_MIGRATIONS="${RUN_MIGRATIONS_ON_STARTUP:-1}"
PORT="${PORT:-8000}"

run_migrations() {
  attempt=1
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    echo "🗄️  Running migrations (attempt ${attempt}/${MAX_RETRIES})..."
    if python manage.py migrate --noinput; then
      echo "✅ Migrations complete."
      return 0
    fi

    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
      echo "⚠️  Migration failed. Retrying in ${SLEEP_SECONDS}s..."
      sleep "$SLEEP_SECONDS"
    fi
    attempt=$((attempt + 1))
  done

  echo "❌ Fatal: migrations failed after ${MAX_RETRIES} attempts. Exiting."
  return 1
}

if [ "$RUN_MIGRATIONS" = "1" ]; then
  run_migrations || { echo "Fatal: migrations failed. Not starting app."; exit 1; }
else
  echo "⏭️  Skipping migrations (RUN_MIGRATIONS_ON_STARTUP=${RUN_MIGRATIONS})."
fi

echo "🏷️  Ensuring default brand exists..."
python manage.py create_default_brand --skip-checks 2>/dev/null || true

echo "📤 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Gunicorn..."
exec gunicorn store.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2 --timeout 120
