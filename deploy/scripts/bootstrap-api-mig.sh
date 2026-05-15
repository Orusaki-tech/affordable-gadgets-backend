#!/usr/bin/env bash
# Bootstrap API MIG instances: Docker + GCS config + compose up (until startup scripts are reliable).
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-gmail-486411}"
ZONE="${GCP_ZONE:-us-central1-a}"
MIG="${API_MIG_NAME:-affordable-gadgets-staging-api-mig}"
BUCKET="${DEPLOY_CONFIG_BUCKET:-affordable-gadgets-staging-deploy-config}"
REGION="${GCP_REGION:-us-central1}"

INSTANCES=$(gcloud compute instance-groups managed list-instances "${MIG}" \
  --region="${REGION}" --project="${PROJECT}" \
  --format="value(instance.scope())" 2>/dev/null | while read -r url; do
    echo "${url##*/}"
  done)

for INSTANCE in ${INSTANCES}; do
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
sudo gsutil -m cp gs://${BUCKET}/staging/api/* /opt/affordable-gadgets/
sudo chmod 600 /opt/affordable-gadgets/api.env
cd /opt/affordable-gadgets && sudo docker rm -f ag-api-web 2>/dev/null || true
sudo docker-compose -f docker-compose.api.yml pull -q && sudo docker-compose -f docker-compose.api.yml up -d
sleep 8
curl -sf http://127.0.0.1:8000/health/ && echo ${INSTANCE}_OK
" || echo "WARN: bootstrap failed for ${INSTANCE}"
done

echo "==> LB health:"
curl -sf --max-time 20 http://$(cd "$(dirname "$0")/../terraform" && terraform output -raw api_lb_ip)/health/ && echo OK || echo "LB not ready yet"
