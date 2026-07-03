#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y docker.io curl ca-certificates gnupg unzip

if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
fi

COMPOSE_VERSION="v2.32.4"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/$${COMPOSE_VERSION}/docker-compose-linux-$$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
systemctl enable docker
systemctl start docker

COMPOSE_ROOT="/opt/affordable-gadgets"
mkdir -p "$${COMPOSE_ROOT}/monitoring/prometheus" \
         "$${COMPOSE_ROOT}/monitoring/grafana/datasources" \
         "$${COMPOSE_ROOT}/monitoring/grafana/dashboards" \
         "$${COMPOSE_ROOT}/monitoring/tunnel"

S3_PREFIX="s3://${deploy_config_bucket}/${environment}/monitoring"
if aws s3 ls "$${S3_PREFIX}/docker-compose.monitoring.yml" >/dev/null 2>&1; then
  aws s3 sync "$${S3_PREFIX}/" "$${COMPOSE_ROOT}/"
fi

cat >/etc/systemd/system/ag-monitoring-compose.service <<'UNIT'
[Unit]
Description=Affordable Gadgets Monitoring Docker Compose
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/affordable-gadgets
ExecStart=/bin/bash -c '/usr/bin/docker compose -f docker-compose.monitoring.yml --env-file monitoring/grafana.env up -d --remove-orphans; /usr/bin/docker compose -f docker-compose.tunnel.yml --env-file monitoring/tunnel/tunnel.env up -d || true'
ExecStop=/usr/bin/docker compose -f docker-compose.monitoring.yml -f docker-compose.tunnel.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ag-monitoring-compose.service

if [[ -f "$${COMPOSE_ROOT}/docker-compose.monitoring.yml" ]]; then
  systemctl start ag-monitoring-compose.service || true
fi
