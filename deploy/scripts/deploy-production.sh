#!/bin/bash
set -euo pipefail

# Deploy production Docker images, compose configs, and trigger MIG rolling restart.
# Usage: ./deploy-production.sh [env=production] [region=us-east1] [--upload-env]
#
#   --upload-env  Also upload deploy/env/api.<env>.env to GCS.
#                 WARNING: this overwrites production secrets in GCS.
#                 Only use when you've intentionally updated the env file.

UPLOAD_ENV=false
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --upload-env) UPLOAD_ENV=true; shift ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

ENV="${POSITIONAL[0]:-production}"
REGION="${POSITIONAL[1]:-us-east1}"
PROJECT="${PROJECT_ID:-gmail-486411}"
BUCKET="affordable-gadgets-${ENV}-deploy-config"
PREFIX="${ENV}"
BACKEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ">>> Building and pushing Docker images ..."

# API
echo "  api/"
gcloud builds submit \
  --tag "us-east1-docker.pkg.dev/${PROJECT}/ag-api/ag-api:${ENV}-latest" \
  "${BACKEND_ROOT}" --project="${PROJECT}" --quiet

# Shop (if Dockerfile.shop exists)
if [[ -f "${BACKEND_ROOT}/Dockerfile.shop" ]]; then
  echo "  shop/"
  gcloud builds submit \
    --tag "us-central1-docker.pkg.dev/${PROJECT}/ag-shop/ag-shop:${ENV}-latest" \
    "${BACKEND_ROOT}" --project="${PROJECT}" --quiet
fi

echo ""
echo ">>> Uploading compose configs to gs://${BUCKET}/${PREFIX}/ ..."

# API — compose only (env uploaded separately to avoid overwriting secrets)
echo "  api/docker-compose.api.yml"
gsutil cp "${BACKEND_ROOT}/deploy/compose/docker-compose.api.yml" "gs://${BUCKET}/${PREFIX}/api/docker-compose.api.yml"

# Shop
echo "  shop/docker-compose.shop.yml"
sed "s/{{environment}}/${ENV}/g" "${BACKEND_ROOT}/deploy/compose/docker-compose.shop.yml" | \
  gsutil cp - "gs://${BUCKET}/${PREFIX}/shop/docker-compose.shop.yml"

# Admin
echo "  admin/docker-compose.admin.yml"
sed "s/{{environment}}/${ENV}/g" "${BACKEND_ROOT}/deploy/compose/docker-compose.admin.yml" | \
  gsutil cp - "gs://${BUCKET}/${PREFIX}/admin/docker-compose.admin.yml"

if [[ "${UPLOAD_ENV}" == "true" ]]; then
  echo "  api/api.env (--upload-env requested)"
  gsutil cp "${BACKEND_ROOT}/deploy/env/api.${ENV}.env" "gs://${BUCKET}/${PREFIX}/api/api.env"
else
  echo "  api/api.env (skipped — use --upload-env to overwrite)"
fi

echo ""
echo ">>> Triggering MIG rolling restart..."
for MIG in api shop admin; do
  MIG_NAME="affordable-gadgets-${ENV}-${MIG}-mig"
  echo "  ${MIG_NAME}"
  gcloud compute instance-groups managed rolling-action replace \
    "${MIG_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT}" \
    --max-surge=1 \
    --max-unavailable=0 2>/dev/null || \
  echo "  (skipped — ${MIG_NAME} not found)"
  sleep 5
done

echo ""
echo ">>> Done. Instances will pick up fresh images within 5 min."
if [[ "${UPLOAD_ENV}" == "false" ]]; then
  echo "    (api.env was NOT uploaded — env changes are not yet deployed)"
fi
