#!/bin/bash
set -euo pipefail
apt-get update -y
apt-get install -y docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker
mkdir -p /opt/affordable-gadgets
cat >/etc/systemd/system/ag-tunnel-compose.service <<'UNIT'
[Unit]
Description=Cloudflare Tunnel Docker Compose
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/affordable-gadgets
ExecStart=/usr/bin/docker compose -f docker-compose.tunnel.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.tunnel.yml down

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ag-tunnel-compose.service || true
