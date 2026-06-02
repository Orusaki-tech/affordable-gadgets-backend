#!/bin/bash
set -euo pipefail
apt-get update -y
apt-get install -y docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker
mkdir -p /opt/affordable-gadgets

# Create systemd service to pull monitoring configs from deploy bucket and run docker compose
cat >/etc/systemd/system/ag-monitoring-compose.service <<'UNIT'
[Unit]
Description=Affordable Gadgets Monitoring Stack (Prometheus + Grafana)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/affordable-gadgets
# Note: This service will be started by deploy-monitoring.sh script via Ansible
# which handles downloading configs and setting environment variables
ExecStart=/usr/bin/docker compose -f docker-compose.monitoring.yml --env-file monitoring/grafana.env up -d --remove-orphans
ExecReload=/usr/bin/docker compose -f docker-compose.monitoring.yml --env-file monitoring/grafana.env up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.monitoring.yml down

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable ag-monitoring-compose.service || true
echo "Monitoring startup script completed. Run deploy-monitoring.sh to deploy the stack."
