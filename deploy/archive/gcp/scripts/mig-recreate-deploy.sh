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
#   DEPLOY_MODE=pull        (default in CI: SSH docker pull only — fast, no VM reboot)
#   DEPLOY_MODE=recreate    (recreate each VM, then pull; slow, quota-safe cold boot)
#   WAIT_TIMEOUT=1800       (seconds per wait-until --stable)
#   HEALTH_URL=             (optional URL to verify after deploy, e.g. https://api.../health/)
set -euo pipefail

ensure_gcloud_ssh() {
  # GitHub Actions runners have no ~/.ssh by default; gcloud ssh prompts and crashes in CI.
  # RSA avoids gcloud "quote_from_bytes() expected bytes" crashes with ed25519 on some SDK versions.
  export CLOUDSDK_CORE_DISABLE_PROMPTS=1
  mkdir -p "${HOME}/.ssh"
  chmod 700 "${HOME}/.ssh"
  if [[ ! -f "${HOME}/.ssh/google_compute_engine" ]]; then
    ssh-keygen -t rsa -b 2048 -f "${HOME}/.ssh/google_compute_engine" -N "" -q
  fi
}

parse_instance_zone() {
  local instance_ref="$1"
  if [[ "${instance_ref}" == *"/zones/"* ]]; then
    local z="${instance_ref#*/zones/}"
    echo "${z%%/*}"
    return 0
  fi
  # Regional MIG list-instances --format="value(name,instance)" returns zone basename only.
  if [[ "${instance_ref}" =~ ^[a-z]+-[a-z]+[0-9]+-[a-z]$ ]]; then
    echo "${instance_ref}"
    return 0
  fi
  return 1
}

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID required}"
REGION="${GCP_REGION:?GCP_REGION required}"
MIG="${MIG_NAME:?MIG_NAME required}"
SERVICE="${SERVICE:-shop}"
ENV_NAME="${ENV_NAME:-production}"
DEPLOY_MODE="${DEPLOY_MODE:-recreate}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-1800}"
AR_HOST="${GCP_REGION}-docker.pkg.dev"

case "${SERVICE}" in
  shop)
    COMPOSE_FILE="docker-compose.shop.yml"
    HEALTH_PORT=3000
    HEALTH_PATH="/"
    GCS_PREFIX="shop"
    ;;
  admin)
    COMPOSE_FILE="docker-compose.admin.yml"
    HEALTH_PORT=80
    HEALTH_PATH="/"
    GCS_PREFIX="admin"
    ;;
  api)
    COMPOSE_FILE="docker-compose.api.yml"
    HEALTH_PORT=8000
    HEALTH_PATH="/health/"
    GCS_PREFIX="api"
    ;;
  *)
    echo "SERVICE must be shop, admin, or api" >&2
    exit 1
    ;;
esac

echo "==> MIG deploy (${DEPLOY_MODE}): ${MIG} (${SERVICE}) project=${PROJECT} region=${REGION}"

if [[ "${DEPLOY_MODE}" == "recreate" ]]; then
  while read -r name; do
    echo "==> Recreating ${name}..."
    gcloud compute instance-groups managed recreate-instances "${MIG}" \
      --instances="${name}" \
      --region="${REGION}" \
      --project="${PROJECT}"
    echo "==> Waiting for MIG stable (timeout=${WAIT_TIMEOUT}s)..."
    if ! gcloud compute instance-groups managed wait-until --stable "${MIG}" \
      --region="${REGION}" \
      --project="${PROJECT}" \
      --timeout="${WAIT_TIMEOUT}"; then
      echo "ERROR: MIG did not stabilize within ${WAIT_TIMEOUT}s." >&2
      gcloud compute instance-groups managed describe "${MIG}" \
        --region="${REGION}" \
        --project="${PROJECT}" \
        --format="yaml(status)" || true
      exit 1
    fi
  done < <(gcloud compute instance-groups managed list-instances "${MIG}" \
    --region="${REGION}" \
    --project="${PROJECT}" \
    --format="value(name)")
elif [[ "${DEPLOY_MODE}" != "pull" ]]; then
  echo "DEPLOY_MODE must be pull or recreate (got: ${DEPLOY_MODE})" >&2
  exit 1
fi

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
if [[ "${SERVICE}" == "api" ]]; then
  sudo docker-compose -f "\${COMPOSE_FILE}" exec -T web python manage.py migrate --noinput || true
  sudo docker-compose -f "\${COMPOSE_FILE}" exec -T web python manage.py sync_product_release_dates --force || true
fi
curl -sf "http://127.0.0.1:${HEALTH_PORT}${HEALTH_PATH}" >/dev/null && echo "\$(hostname)_OK" || echo "\$(hostname)_WARN_health"
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
  if [[ "${DEPLOY_MODE}" == "pull" ]]; then
    echo "ERROR: image pull failed on one or more instances." >&2
    exit 1
  fi
  echo "WARN: one or more image pulls failed; instance startup scripts may still have pulled production-latest on recreate." >&2
fi

if [[ -n "${HEALTH_URL:-}" ]]; then
  echo "==> Verifying ${HEALTH_URL}..."
  for attempt in 1 2 3 4 5 6; do
    if curl -sf --max-time 20 "${HEALTH_URL}" >/dev/null; then
      echo "==> Health check OK"
      break
    fi
    if [[ "${attempt}" -eq 6 ]]; then
      echo "ERROR: health check failed after 6 attempts: ${HEALTH_URL}" >&2
      exit 1
    fi
    echo "==> Health check attempt ${attempt} failed; retrying in 15s..."
    sleep 15
  done
fi

echo "==> MIG deploy complete (${DEPLOY_MODE})."
