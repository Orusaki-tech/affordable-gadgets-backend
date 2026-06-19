#!/usr/bin/env bash
# Quota-safe MIG deploy: recreate one instance at a time, then pull latest image on each VM.
# Use from CI or manually after pushing to Artifact Registry.
#
# Required env:
#   GCP_PROJECT_ID, GCP_REGION, MIG_NAME
# Optional:
#   SERVICE=shop|admin|api  (compose file + health port; default shop)
#   DEPLOY_CONFIG_BUCKET    (if set, refresh compose from GCS before pull)
#   ENV_NAME=production     (GCS prefix under bucket)
#   SKIP_IMAGE_PULL=1       (recreate only, no SSH pull)
#   WAIT_TIMEOUT=900        (seconds per wait-until --stable)
set -euo pipefail

ensure_gcloud_ssh() {
  # GitHub Actions runners have no ~/.ssh by default; gcloud ssh prompts and crashes in CI.
  export CLOUDSDK_CORE_DISABLE_PROMPTS=1
  mkdir -p "${HOME}/.ssh"
  chmod 700 "${HOME}/.ssh"
  if [[ ! -f "${HOME}/.ssh/google_compute_engine" ]]; then
    ssh-keygen -t ed25519 -f "${HOME}/.ssh/google_compute_engine" -N "" -q
  fi
}

parse_instance_zone() {
  local instance_url="$1"
  if [[ "${instance_url}" == *"/zones/"* ]]; then
    local z="${instance_url#*/zones/}"
    echo "${z%%/*}"
    return 0
  fi
  return 1
}

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID required}"
REGION="${GCP_REGION:?GCP_REGION required}"
MIG="${MIG_NAME:?MIG_NAME required}"
SERVICE="${SERVICE:-shop}"
ENV_NAME="${ENV_NAME:-production}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-900}"
AR_HOST="${GCP_REGION}-docker.pkg.dev"

case "${SERVICE}" in
  shop)
    COMPOSE_FILE="docker-compose.shop.yml"
    HEALTH_PORT=3000
    GCS_PREFIX="shop"
    ;;
  admin)
    COMPOSE_FILE="docker-compose.admin.yml"
    HEALTH_PORT=80
    GCS_PREFIX="admin"
    ;;
  api)
    COMPOSE_FILE="docker-compose.api.yml"
    HEALTH_PORT=8000
    GCS_PREFIX="api"
    ;;
  *)
    echo "SERVICE must be shop, admin, or api" >&2
    exit 1
    ;;
esac

echo "==> MIG recreate deploy: ${MIG} (${SERVICE}) project=${PROJECT} region=${REGION}"

while read -r name; do
  echo "==> Recreating ${name}..."
  gcloud compute instance-groups managed recreate-instances "${MIG}" \
    --instances="${name}" \
    --region="${REGION}" \
    --project="${PROJECT}"
  echo "==> Waiting for MIG stable..."
  gcloud compute instance-groups managed wait-until --stable "${MIG}" \
    --region="${REGION}" \
    --project="${PROJECT}" \
    --timeout="${WAIT_TIMEOUT}"
done < <(gcloud compute instance-groups managed list-instances "${MIG}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --format="value(name)")

if [[ "${SKIP_IMAGE_PULL:-}" == "1" ]]; then
  echo "==> SKIP_IMAGE_PULL=1; done."
  exit 0
fi

echo "==> Pulling latest image on each instance..."
ensure_gcloud_ssh
PULL_FAILED=0
while read -r inst_name instance_url; do
  zone="$(parse_instance_zone "${instance_url}" || true)"
  if [[ -z "${zone}" ]]; then
    echo "WARN: could not parse zone for ${inst_name}; skipping image pull" >&2
    PULL_FAILED=1
    continue
  fi
  echo "==> Image pull on ${inst_name} (${zone})..."
  if ! gcloud compute ssh "${inst_name}" \
    --zone="${zone}" \
    --project="${PROJECT}" \
    --tunnel-through-iap \
    --quiet \
    --command="$(cat <<REMOTE
set -e
export DEBIAN_FRONTEND=noninteractive
COMPOSE_ROOT="/opt/affordable-gadgets"
COMPOSE_FILE="${COMPOSE_FILE}"
BUCKET="${DEPLOY_CONFIG_BUCKET:-}"
ENV_NAME="${ENV_NAME}"
GCS_PREFIX="${GCS_PREFIX}"
AR_HOST="${AR_HOST}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not installed on \$(hostname); skipping pull"
  exit 0
fi

if command -v gcloud >/dev/null 2>&1; then
  sudo gcloud auth configure-docker \${AR_HOST} --quiet 2>/dev/null || true
fi

sudo mkdir -p "\${COMPOSE_ROOT}"
if [[ -n "\${BUCKET}" ]] && command -v gsutil >/dev/null 2>&1; then
  if gsutil -q stat "gs://\${BUCKET}/\${ENV_NAME}/\${GCS_PREFIX}/\${COMPOSE_FILE}" 2>/dev/null; then
    sudo gsutil -q cp "gs://\${BUCKET}/\${ENV_NAME}/\${GCS_PREFIX}/\${COMPOSE_FILE}" "\${COMPOSE_ROOT}/"
  fi
fi

if [[ ! -f "\${COMPOSE_ROOT}/\${COMPOSE_FILE}" ]]; then
  echo "No compose file at \${COMPOSE_ROOT}/\${COMPOSE_FILE}; skipping pull"
  exit 0
fi

cd "\${COMPOSE_ROOT}"
sudo docker-compose -f "\${COMPOSE_FILE}" pull -q
sudo docker-compose -f "\${COMPOSE_FILE}" up -d
sleep 10
curl -sf "http://127.0.0.1:${HEALTH_PORT}/" >/dev/null && echo "\$(hostname)_OK" || echo "\$(hostname)_WARN_health"
REMOTE
)"; then
    echo "WARN: image pull failed for ${inst_name}" >&2
    PULL_FAILED=1
  fi
done < <(gcloud compute instance-groups managed list-instances "${MIG}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --format="value(name,instance)")

if [[ "${PULL_FAILED}" -eq 1 ]]; then
  echo "WARN: one or more image pulls failed; instance startup scripts may still have pulled production-latest on recreate." >&2
fi

echo "==> MIG recreate deploy complete."
