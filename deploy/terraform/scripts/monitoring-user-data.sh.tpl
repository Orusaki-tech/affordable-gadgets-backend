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

# 2 GB swap — prevents OOM kills on Prometheus + Grafana
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -w vm.swappiness=10
grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf

COMPOSE_ROOT="/opt/affordable-gadgets"
mkdir -p "$${COMPOSE_ROOT}/monitoring/prometheus" \
         "$${COMPOSE_ROOT}/monitoring/grafana/datasources" \
         "$${COMPOSE_ROOT}/monitoring/grafana/dashboards" \
         "$${COMPOSE_ROOT}/scripts"

S3_PREFIX="s3://${deploy_config_bucket}/${environment}/monitoring"
if aws s3 ls "$${S3_PREFIX}/docker-compose.monitoring.yml" >/dev/null 2>&1; then
  aws s3 sync "$${S3_PREFIX}/" "$${COMPOSE_ROOT}/"
fi
if aws s3 ls "$${S3_PREFIX}/scripts/monitoring-watchdog.sh" >/dev/null 2>&1; then
  aws s3 cp "$${S3_PREFIX}/scripts/monitoring-watchdog.sh" "$${COMPOSE_ROOT}/scripts/monitoring-watchdog.sh"
  chmod +x "$${COMPOSE_ROOT}/scripts/monitoring-watchdog.sh"
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
ExecStart=/usr/bin/docker compose -f docker-compose.monitoring.yml --env-file monitoring/grafana.env up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.monitoring.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT

cat >/etc/systemd/system/ag-monitoring-watchdog.service <<'UNIT'
[Unit]
Description=Monitoring stack health watchdog

[Service]
Type=oneshot
Environment=COMPOSE_ROOT=/opt/affordable-gadgets
ExecStart=/opt/affordable-gadgets/scripts/monitoring-watchdog.sh
UNIT

cat >/etc/systemd/system/ag-monitoring-watchdog.timer <<'UNIT'
[Unit]
Description=Run monitoring watchdog every 2 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable ag-monitoring-compose.service ag-monitoring-watchdog.timer

if [[ -f "$${COMPOSE_ROOT}/docker-compose.monitoring.yml" ]]; then
  systemctl start ag-monitoring-compose.service || true
fi
if [[ -x "$${COMPOSE_ROOT}/scripts/monitoring-watchdog.sh" ]]; then
  systemctl start ag-monitoring-watchdog.timer || true
fi
