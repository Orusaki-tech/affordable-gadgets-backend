#!/usr/bin/env bash
# Bootstrap shop MIG instances: Docker + GCS compose + up (until startup scripts are reliable).
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-project-07850c05-c54d-486b-80a}"
ZONE="${GCP_ZONE:-us-central1-a}"
MIG="${SHOP_MIG_NAME:-affordable-gadgets-staging-shop-mig}"
BUCKET="${DEPLOY_CONFIG_BUCKET:-affordable-gadgets-staging-deploy-config}"
REGION="${GCP_REGION:-us-central1}"

gcloud compute instance-groups managed list-instances "${MIG}" \
  --region="${REGION}" --project="${PROJECT}" \
  --format="value(instance.scope())" | while read -r url; do
  INSTANCE="${url##*/}"
  echo "==> Bootstrap ${INSTANCE}..."
  gcloud compute ssh "${INSTANCE}" --zone="${ZONE}" --project="${PROJECT}" --tunnel-through-iap --command="
set -e
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker.io curl
  sudo systemctl enable docker && sudo systemctl start docker
  COMPOSE_VER=v2.24.5
  sudo curl -fsSL https://github.com/docker/compose/releases/download/\${COMPOSE_VER}/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi
if ! command -v gsutil >/dev/null; then
  echo deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  sudo apt-get update -qq && sudo apt-get install -y -qq google-cloud-cli
fi
sudo gcloud auth configure-docker us-central1-docker.pkg.dev --quiet 2>/dev/null || true
sudo mkdir -p /opt/affordable-gadgets
sudo gsutil -q cp gs://${BUCKET}/staging/shop/docker-compose.shop.yml /opt/affordable-gadgets/
cd /opt/affordable-gadgets
sudo docker rm -f ag-shop 2>/dev/null || true
sudo docker-compose -f docker-compose.shop.yml pull -q
sudo docker-compose -f docker-compose.shop.yml up -d
sleep 15
curl -sf http://127.0.0.1:3000/ >/dev/null && echo ${INSTANCE}_OK || echo ${INSTANCE}_FAIL
" || echo "WARN: bootstrap failed for ${INSTANCE}"
done

SHOP_LB="$(cd "$(dirname "$0")/../terraform" && terraform output -raw shop_lb_ip 2>/dev/null || true)"
if [[ -n "${SHOP_LB}" ]]; then
  echo "==> Shop LB:"
  curl -sf --max-time 20 "http://${SHOP_LB}/" >/dev/null && echo OK || echo "not ready"
fi
