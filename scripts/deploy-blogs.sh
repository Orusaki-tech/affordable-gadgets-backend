#!/usr/bin/env bash
set -eu

# deploy-blogs.sh — Load blog article fixtures into production.
#
# Usage:
#   export DJANGO_ADMIN_TOKEN="<token from api/auth/token/login/>"
#   ./scripts/deploy-blogs.sh [batch-name]
#
# If no batch name is provided, loads all unprocessed batches.
#
# Requires:
#   - gcloud configured with access to the MIG
#   - DJANGO_ADMIN_TOKEN env var (DRF auth token for the admin user)
#
# Runs the load_blog_batch management command on one of the production
# API instances via gcloud compute ssh.

BATCH="${1:-}"

PROJECT="gmail-486411"
REGION="us-east1"
ZONE="us-east1-b"
MIG="affordable-gadgets-production-api-mig"

echo "🔍 Finding a running API instance..."
INSTANCE=$(gcloud compute instance-groups managed list-instances "${MIG}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --format="value(NAME)" \
  --limit=1)

if [ -z "${INSTANCE}" ]; then
  echo "❌ No running API instances found in ${MIG}"
  exit 1
fi

echo "✅ Found instance: ${INSTANCE}"

CMD="python manage.py load_blog_batch"
if [ -n "${BATCH}" ]; then
  CMD="${CMD} --batch ${BATCH}"
fi

echo "🚀 Running: ${CMD}"

gcloud compute ssh "${INSTANCE}" \
  --project="${PROJECT}" \
  --zone="${ZONE}" \
  --tunnel-through-iap \
  --command="docker exec \$(docker ps -q -f name=web) ${CMD}"

echo "✅ Batch loaded successfully!"
echo "   Visit: https://www.affordable-gadgetske.com/products/<slug>/blog"
