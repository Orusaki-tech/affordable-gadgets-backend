#!/usr/bin/env bash
# Dump legacy VM Postgres and restore into Cloud SQL (via Cloud SQL Auth Proxy).
set -euo pipefail

LEGACY_INSTANCE="${LEGACY_INSTANCE:-affordable-gadgets-backend}"
LEGACY_ZONE="${LEGACY_ZONE:-us-central1-a}"
LEGACY_PROJECT="${LEGACY_PROJECT:-gmail-486411}"
LEGACY_PG_CONTAINER="${LEGACY_PG_CONTAINER:-affordable-gadgets-postgres}"
DUMP_LOCAL="${DUMP_LOCAL:-./affordable_gadgets.dump}"

TF_DIR="$(cd "$(dirname "$0")/../terraform" && pwd)"
CONN="$(cd "${TF_DIR}" && terraform output -raw cloud_sql_connection_name 2>/dev/null || true)"
DB_USER="${DB_USER:-affordable}"
DB_NAME="${DB_NAME:-affordable_gadgets}"

if [[ -z "${CONN}" ]]; then
  echo "cloud_sql_connection_name missing — run terraform apply with platform_enabled=true first." >&2
  exit 1
fi

echo "==> Dump from legacy VM ${LEGACY_INSTANCE}..."
gcloud compute ssh "${LEGACY_INSTANCE}" \
  --zone="${LEGACY_ZONE}" --project="${LEGACY_PROJECT}" \
  --command="docker exec ${LEGACY_PG_CONTAINER} pg_dump -U ${DB_USER} -Fc ${DB_NAME} > /tmp/affordable_gadgets.dump"

gcloud compute scp "${LEGACY_INSTANCE}:/tmp/affordable_gadgets.dump" "${DUMP_LOCAL}" \
  --zone="${LEGACY_ZONE}" --project="${LEGACY_PROJECT}"

echo "==> Start Cloud SQL Auth Proxy..."
PROXY_BIN="${PROXY_BIN:-cloud-sql-proxy}"
if ! command -v "${PROXY_BIN}" >/dev/null 2>&1; then
  echo "Install cloud-sql-proxy: https://cloud.google.com/sql/docs/postgres/connect-auth-proxy" >&2
  exit 1
fi

"${PROXY_BIN}" "${CONN}" &
PROXY_PID=$!
trap 'kill ${PROXY_PID} 2>/dev/null || true' EXIT
sleep 5

DB_PASSWORD="${DB_PASSWORD:-}"
if [[ -z "${DB_PASSWORD}" ]]; then
  DB_PASSWORD="$(cd "${TF_DIR}" && terraform output -raw cloud_sql_db_password)"
fi
export PGPASSWORD="${DB_PASSWORD}"

echo "==> Restore to Cloud SQL..."
pg_restore -h 127.0.0.1 -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists -Fc "${DUMP_LOCAL}" || {
  echo "If database is empty, create it first in Cloud SQL console or:"
  echo "  createdb -h 127.0.0.1 -U ${DB_USER} ${DB_NAME}"
  exit 1
}

echo "==> Done. Run ansible api playbook and smoke: curl https://api-staging.../health/"
