#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y docker.io curl ca-certificates gnupg unzip

# AWS CLI v2
if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
fi

# Docker Compose plugin (not in Ubuntu default repos)
COMPOSE_VERSION="v2.32.4"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/$${COMPOSE_VERSION}/docker-compose-linux-$$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
systemctl enable docker
systemctl start docker

COMPOSE_ROOT="/opt/affordable-gadgets"
mkdir -p "$${COMPOSE_ROOT}"
S3_PREFIX="s3://${deploy_config_bucket}/${environment}/api"
ECR_REGISTRY="${ecr_registry}"

aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin "$${ECR_REGISTRY}"

if aws s3 ls "$${S3_PREFIX}/docker-compose.api.yml" >/dev/null 2>&1; then
  aws s3 cp "$${S3_PREFIX}/docker-compose.api.yml" "$${COMPOSE_ROOT}/docker-compose.api.yml"
  aws s3 cp "$${S3_PREFIX}/api.env" "$${COMPOSE_ROOT}/api.env" || true
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
ExecStart=/usr/bin/docker compose -f docker-compose.api.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.api.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ag-api-compose.service

if [[ -f "$${COMPOSE_ROOT}/docker-compose.api.yml" ]]; then
  systemctl start ag-api-compose.service || docker compose -f "$${COMPOSE_ROOT}/docker-compose.api.yml" up -d
fi
