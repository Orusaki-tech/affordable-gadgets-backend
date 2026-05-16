#!/bin/bash
set -euo pipefail

# Deploy production compose configs to GCS and trigger MIG rolling restart.
# Usage: ./deploy-production.sh [env=production]

ENV="${1:-production}"
ZONE="${2:-us-east1-b}"
PROJECT="${PROJECT_ID:-gmail-486411}"
BUCKET="affordable-gadgets-${ENV}-deploy-config"
PREFIX="${ENV}"

echo ">>> Uploading compose configs to gs://${BUCKET}/${PREFIX}/ ..."

# API
echo "  api/"
gsutil cp deploy/compose/docker-compose.api.yml "gs://${BUCKET}/${PREFIX}/api/docker-compose.api.yml"
gsutil cp deploy/env/api."${ENV}".env "gs://${BUCKET}/${PREFIX}/api/api.env"

# Shop
echo "  shop/"
sed "s/{{environment}}/${ENV}/g" deploy/compose/docker-compose.shop.yml | \
  gsutil cp - "gs://${BUCKET}/${PREFIX}/shop/docker-compose.shop.yml"

# Admin
echo "  admin/"
sed "s/{{environment}}/${ENV}/g" deploy/compose/docker-compose.admin.yml | \
  gsutil cp - "gs://${BUCKET}/${PREFIX}/admin/docker-compose.admin.yml"

echo ""
echo ">>> Triggering MIG rolling restart..."
for MIG in api shop admin; do
  echo "  affordable-gadgets-${ENV}-${MIG}-mig"
  gcloud compute instances list \
    --project="${PROJECT}" \
    --filter="name~affordable-gadgets-${ENV}-${MIG}-" \
    --format="value(name,zone)" 2>/dev/null \
  | while read -r INSTANCE ZONE; do
      gcloud compute instance-groups managed delete-instances \
        "affordable-gadgets-${ENV}-${MIG}-mig" \
        --instances="${INSTANCE}" \
        --region="${ZONE%-*}" \
        --project="${PROJECT}" 2>/dev/null || true
    done
  sleep 5
done

echo ""
echo ">>> Done. New instances will start with fresh config within 5 min."
