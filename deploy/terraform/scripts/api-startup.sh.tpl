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

gcloud auth configure-docker --quiet 2>/dev/null || true

# gcloud/gsutil for deploy config sync
if ! command -v gsutil >/dev/null 2>&1; then
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  apt-get update -y
  apt-get install -y google-cloud-cli
fi

COMPOSE_ROOT="/opt/affordable-gadgets"
mkdir -p "$${COMPOSE_ROOT}"
PREFIX="gs://${deploy_config_bucket}/${environment}/api"

if gsutil -q stat "$${PREFIX}/docker-compose.api.yml" 2>/dev/null; then
  gsutil cp "$${PREFIX}/docker-compose.api.yml" "$${COMPOSE_ROOT}/docker-compose.api.yml" 2>/dev/null || true
  gsutil cp "$${PREFIX}/api.env" "$${COMPOSE_ROOT}/api.env" 2>/dev/null || true
  chmod 600 "$${COMPOSE_ROOT}/api.env" 2>/dev/null || true
fi

cat >/etc/systemd/system/ag-api-compose.service <<'UNIT'
[Unit]
Description=Affordable Gadgets API Docker Compose
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/affordable-gadgets
ExecStart=/usr/local/bin/docker-compose -f docker-compose.api.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.api.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ag-api-compose.service || true

if [[ -f "$${COMPOSE_ROOT}/docker-compose.api.yml" ]]; then
  systemctl start ag-api-compose.service || /usr/local/bin/docker-compose -f "$${COMPOSE_ROOT}/docker-compose.api.yml" up -d
fi
