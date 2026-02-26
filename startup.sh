#!/usr/bin/env sh
set -eu

# Resilient startup for transient DB/pooler failures.
# - Retries migrations with backoff.
# - Starts Gunicorn even if migrations keep failing, so the app can still boot.

MAX_RETRIES="${MIGRATE_MAX_RETRIES:-8}"
SLEEP_SECONDS="${MIGRATE_RETRY_SLEEP_SECONDS:-10}"
RUN_MIGRATIONS="${RUN_MIGRATIONS_ON_STARTUP:-1}"

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

  echo "⚠️  Migrations failed after ${MAX_RETRIES} attempts. Starting app anyway."
  return 1
}

if [ "$RUN_MIGRATIONS" = "1" ]; then
  run_migrations || true
else
  echo "⏭️  Skipping migrations (RUN_MIGRATIONS_ON_STARTUP=${RUN_MIGRATIONS})."
fi

echo "🚀 Starting Gunicorn..."
exec gunicorn store.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2 --timeout 120
