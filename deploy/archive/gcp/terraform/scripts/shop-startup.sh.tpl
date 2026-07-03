#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y docker.io curl ca-certificates gnupg
COMPOSE_VER=v2.24.5
curl -fsSL "https://github.com/docker/compose/releases/download/$${COMPOSE_VER}/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
systemctl enable docker
systemctl start docker

if ! command -v gsutil >/dev/null 2>&1; then
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  apt-get update -y
  apt-get install -y google-cloud-cli
fi

# Authenticate Docker to Artifact Registry using the instance's service account
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-east1-docker.pkg.dev

COMPOSE_ROOT="/opt/affordable-gadgets"
mkdir -p "$${COMPOSE_ROOT}"
PREFIX="gs://${deploy_config_bucket}/${environment}/shop"

if gsutil -q stat "$${PREFIX}/docker-compose.shop.yml" 2>/dev/null; then
  gsutil -m cp "$${PREFIX}/docker-compose.shop.yml" "$${COMPOSE_ROOT}/"
fi

cat >/etc/systemd/system/ag-shop-compose.service <<'UNIT'
[Unit]
Description=Affordable Gadgets Shop Docker Compose
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/affordable-gadgets
ExecStart=/usr/local/bin/docker-compose -f docker-compose.shop.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.shop.yml down

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ag-shop-compose.service || true

if [[ -f "$${COMPOSE_ROOT}/docker-compose.shop.yml" ]]; then
  systemctl start ag-shop-compose.service || /usr/local/bin/docker-compose -f "$${COMPOSE_ROOT}/docker-compose.shop.yml" up -d
fi
