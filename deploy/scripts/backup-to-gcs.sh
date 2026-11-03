#!/usr/bin/env bash
# Backup GCP API VM state to Google Cloud Storage, then prune local disk pressure.
#
# Usage (on the VM as root/sudo):
#   BACKUP_BUCKET=ag-backups-bc0f5694 ./deploy/scripts/backup-to-gcs.sh
#
# Env:
#   BACKUP_BUCKET   GCS bucket name (no gs:// prefix). Required.
#   DEPLOY_PATH     App root on the VM (default: /opt/affordable-gadgets)
#   KEEP_LOCAL_DAYS Delete local /var/backups/ag older than N days (default: 2)
#   SKIP_UPLOAD     If 1, only create local archives (default: 0)

set -euo pipefail

BACKUP_BUCKET="${BACKUP_BUCKET:?Set BACKUP_BUCKET}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/affordable-gadgets}"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-2}"
SKIP_UPLOAD="${SKIP_UPLOAD:-0}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
HOST="$(hostname -s 2>/dev/null || echo ag-api)"
LOCAL_ROOT="/var/backups/ag/${STAMP}"
REMOTE_PREFIX="gs://${BACKUP_BUCKET}/${HOST}/${STAMP}"

mkdir -p "${LOCAL_ROOT}"/{db,config,logs,disk}
chmod 700 "${LOCAL_ROOT}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "Starting backup → ${REMOTE_PREFIX}"
df -h / | tee "${LOCAL_ROOT}/disk/df-before.txt"

# --- Detect postgres container ---
PG_CONTAINER=""
for name in affordable-gadgets-postgres ag-postgres postgres; do
  if docker ps --format '{{.Names}}' | grep -qx "$name"; then
    PG_CONTAINER="$name"
    break
  fi
done

# --- Database dump ---
if [[ -n "${PG_CONTAINER}" ]]; then
  log "Dumping Postgres from ${PG_CONTAINER}"
  # Prefer credentials inside the container env; fall back to affordable/affordable.
  PGUSER="$(docker exec "${PG_CONTAINER}" printenv POSTGRES_USER 2>/dev/null || echo affordable)"
  PGDATABASE="$(docker exec "${PG_CONTAINER}" printenv POSTGRES_DB 2>/dev/null || echo affordable_gadgets)"
  docker exec "${PG_CONTAINER}" pg_dump -U "${PGUSER}" -d "${PGDATABASE}" -Fc --no-owner --no-acl \
    > "${LOCAL_ROOT}/db/${PGDATABASE}.dump"
  docker exec "${PG_CONTAINER}" pg_dump -U "${PGUSER}" -d "${PGDATABASE}" --no-owner --no-acl \
    | gzip -c > "${LOCAL_ROOT}/db/${PGDATABASE}.sql.gz"
  sha256sum "${LOCAL_ROOT}/db/"* > "${LOCAL_ROOT}/db/SHA256SUMS"
else
  log "WARNING: no postgres container found; skipping DB dump"
fi

# --- Config / app snapshot (no secrets in filenames; .env may contain secrets → encrypted-ish mode is overkill; store privately in GCS) ---
log "Archiving config and compose files"
CONFIG_TAR="${LOCAL_ROOT}/config/deploy-config.tar.gz"
if [[ -d "${DEPLOY_PATH}" ]]; then
  tar -C "${DEPLOY_PATH}" -czf "${CONFIG_TAR}" \
    --exclude='app/.git' \
    --exclude='**/node_modules' \
    --exclude='**/__pycache__' \
    --exclude='**/*.pyc' \
    --warning=no-file-changed \
    . 2>/dev/null || tar -C "${DEPLOY_PATH}" -czf "${CONFIG_TAR}" \
      --exclude='app/.git' \
      --exclude='**/node_modules' \
      --exclude='**/__pycache__' \
      .
fi

# --- Docker / journal logs (trimmed) ---
log "Collecting logs"
{
  docker ps -a
  echo '---'
  docker system df
} > "${LOCAL_ROOT}/logs/docker-ps.txt" 2>&1 || true

for c in $(docker ps --format '{{.Names}}' 2>/dev/null); do
  docker logs --tail 2000 "$c" > "${LOCAL_ROOT}/logs/${c}.log" 2>&1 || true
done
journalctl -u docker --no-pager -n 500 > "${LOCAL_ROOT}/logs/journal-docker.txt" 2>/dev/null || true
dmesg -T 2>/dev/null | tail -n 200 > "${LOCAL_ROOT}/logs/dmesg-tail.txt" || true

# --- Manifest ---
{
  echo "stamp=${STAMP}"
  echo "host=${HOST}"
  echo "deploy_path=${DEPLOY_PATH}"
  echo "pg_container=${PG_CONTAINER}"
  uname -a
  df -h
} > "${LOCAL_ROOT}/MANIFEST.txt"

# --- Upload ---
if [[ "${SKIP_UPLOAD}" != "1" ]]; then
  if ! command -v gcloud >/dev/null 2>&1 && ! command -v gsutil >/dev/null 2>&1; then
    log "ERROR: gcloud/gsutil missing; cannot upload"
    exit 1
  fi
  log "Uploading to ${REMOTE_PREFIX}"
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp -r "${LOCAL_ROOT}/*" "${REMOTE_PREFIX}/"
  else
    gsutil -m cp -r "${LOCAL_ROOT}/*" "${REMOTE_PREFIX}/"
  fi
  echo "${REMOTE_PREFIX}" > /var/backups/ag/LATEST.txt
  log "Upload complete"
else
  log "SKIP_UPLOAD=1 — left archives in ${LOCAL_ROOT}"
fi

# --- Free disk after successful upload ---
log "Pruning docker / journals to relieve disk"
journalctl --vacuum-size=80M >/dev/null 2>&1 || true
find /var/lib/docker/containers -name '*-json.log' -size +20M -exec truncate -s 0 {} \; 2>/dev/null || true
docker container prune -f >/dev/null 2>&1 || true
docker image prune -af >/dev/null 2>&1 || true
docker builder prune -af >/dev/null 2>&1 || true

# Keep only recent local backup dirs
find /var/backups/ag -mindepth 1 -maxdepth 1 -type d -mtime "+${KEEP_LOCAL_DAYS}" -exec rm -rf {} + 2>/dev/null || true

df -h / | tee "${LOCAL_ROOT}/disk/df-after.txt" || df -h /
log "Done. Remote: ${REMOTE_PREFIX}"
