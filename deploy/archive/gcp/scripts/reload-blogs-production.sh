#!/usr/bin/env bash
set -euo pipefail

# reload-blogs-production.sh — Reload blog articles into production Cloud SQL.
#
# Usage:
#   export CLOUD_SQL_CONNECTION_NAME="project:region:instance"
#   export PRODUCTION_DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/affordable_gadgets"
#   ./scripts/reload-blogs-production.sh
#
# Or with proxy already running:
#   DATABASE_URL="$PRODUCTION_DATABASE_URL" ./scripts/reload-blogs-production.sh
#
# Optional: merge from a Cloud SQL clone first:
#   export RESTORE_DATABASE_URL="postgresql://..."
#   python manage.py merge_from_restore_db --dry-run
#   python manage.py merge_from_restore_db

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -z "${PRODUCTION_DATABASE_URL:-}" ]]; then
    echo "ERROR: Set DATABASE_URL or PRODUCTION_DATABASE_URL" >&2
    exit 1
  fi
  export DATABASE_URL="${PRODUCTION_DATABASE_URL}"
fi

PROXY_PID=""
if [[ -n "${CLOUD_SQL_CONNECTION_NAME:-}" ]] && ! nc -z 127.0.0.1 5432 2>/dev/null; then
  PROXY_BIN="${PROXY_BIN:-cloud-sql-proxy}"
  if ! command -v "${PROXY_BIN}" >/dev/null 2>&1; then
    echo "ERROR: cloud-sql-proxy not found; start proxy manually or install it." >&2
    exit 1
  fi
  echo "Starting Cloud SQL Auth Proxy for ${CLOUD_SQL_CONNECTION_NAME}..."
  "${PROXY_BIN}" "${CLOUD_SQL_CONNECTION_NAME}" &
  PROXY_PID=$!
  trap 'kill ${PROXY_PID} 2>/dev/null || true' EXIT
  sleep 5
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-store.settings_production}"
export SECRET_KEY="${SECRET_KEY:-blog-reload-local-only}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost}"
export FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-https://shop.affordable-gadgetske.com}"

echo "Auditing catalog vs blog JSON..."
python manage.py audit_blog_recovery

echo ""
echo "Dry run load_blog_batch..."
python manage.py load_blog_batch --dry-run

echo ""
echo "Loading all blog batches (--force)..."
python manage.py load_blog_batch --force

echo ""
echo "Post-load audit..."
python manage.py audit_blog_recovery

echo ""
echo "Done. Verify: curl -s 'https://api.affordable-gadgetske.com/api/v1/public/products/?page_size=5' | grep has_published_article"
