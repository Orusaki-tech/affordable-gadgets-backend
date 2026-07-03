#!/usr/bin/env bash
# Sync production Cloud SQL data into Render Postgres (external URL).
#
# Usage:
#   export CLOUD_SQL_CONNECTION_NAME="project-07850c05-c54d-486b-80a:us-east1:affordable-gadgets-production-pg"
#   export PRODUCTION_DATABASE_URL="postgresql://USER:PASS@127.0.0.1:5432/affordable_gadgets"
#   export RENDER_DATABASE_URL="postgresql://USER:PASS@dpg-....oregon-postgres.render.com:5432/DB?sslmode=require"
#   ./scripts/sync-gcp-to-render-postgres.sh
#
# Optional:
#   SKIP_RESTORE=1   — only dump to ./tmp/ag_prod.dump
#   SKIP_DUMP=1      — restore existing ./tmp/ag_prod.dump only

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
DUMP="${ROOT}/tmp/ag_prod.dump"
mkdir -p "${ROOT}/tmp"

if [[ -z "${RENDER_DATABASE_URL:-}" ]]; then
  echo "ERROR: Set RENDER_DATABASE_URL (Render Postgres external URL with ?sslmode=require)" >&2
  exit 1
fi

PROXY_PID=""
cleanup() {
  [[ -n "${PROXY_PID}" ]] && kill "${PROXY_PID}" 2>/dev/null || true
}
trap cleanup EXIT

rewrite_db_url_for_proxy() {
  python3 - <<'PY'
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

raw = os.environ.get("PRODUCTION_DATABASE_URL", "").strip()
if not raw:
    raise SystemExit("PRODUCTION_DATABASE_URL is empty")
parsed = urlparse(raw)
port = parsed.port or 5432
query = dict(parse_qsl(parsed.query, keep_blank_values=True))
query.setdefault("sslmode", "disable")
netloc = f"{parsed.username}:{parsed.password}@127.0.0.1:{port}"
print(urlunparse(parsed._replace(netloc=netloc, query=urlencode(query))))
PY
}

if [[ "${SKIP_DUMP:-0}" != "1" ]]; then
  if [[ -z "${PRODUCTION_DATABASE_URL:-}" ]]; then
    echo "ERROR: Set PRODUCTION_DATABASE_URL (Cloud SQL credentials; host is rewritten to 127.0.0.1 for proxy)" >&2
    exit 1
  fi
  PROXY_DATABASE_URL="$(rewrite_db_url_for_proxy)"
  if [[ -n "${CLOUD_SQL_CONNECTION_NAME:-}" ]] && ! nc -z 127.0.0.1 5432 2>/dev/null; then
    PROXY_BIN="${PROXY_BIN:-cloud-sql-proxy}"
    echo "Starting Cloud SQL Auth Proxy..."
    "${PROXY_BIN}" "${CLOUD_SQL_CONNECTION_NAME}" --port=5432 &
    PROXY_PID=$!
    sleep 5
  fi
  echo "Dumping production database to ${DUMP}..."
  pg_dump "${PROXY_DATABASE_URL}" -Fc --no-owner --no-acl -f "${DUMP}"
  echo "Dump complete ($(du -h "${DUMP}" | cut -f1))"
fi

if [[ "${SKIP_RESTORE:-0}" == "1" ]]; then
  echo "SKIP_RESTORE=1 — done after dump."
  exit 0
fi

if [[ ! -f "${DUMP}" ]]; then
  echo "ERROR: Dump not found at ${DUMP}" >&2
  exit 1
fi

echo "Restoring into Render Postgres (this replaces existing data)..."
pg_restore -d "${RENDER_DATABASE_URL}" --clean --if-exists --no-owner --no-acl "${DUMP}" || true

export DATABASE_URL="${RENDER_DATABASE_URL}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-store.settings_production}"
export SECRET_KEY="${SECRET_KEY:-render-sync-local-only}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost}"
export FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-https://affordable-gadgetske.com}"

echo "Running migrations on Render Postgres..."
python3 manage.py migrate --noinput
python3 manage.py create_default_brand --skip-checks 2>/dev/null || true

echo "Verify counts:"
python3 manage.py shell -c "
from inventory.models import Product, ProductArticle
print('products', Product.objects.count())
print('articles', ProductArticle.objects.count())
"

echo "Done. Set Render web service DATABASE_URL to the same RENDER_DATABASE_URL and redeploy."
