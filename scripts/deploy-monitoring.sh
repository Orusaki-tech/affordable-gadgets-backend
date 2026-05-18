#!/usr/bin/env bash
# Deploy monitoring stack (Prometheus + Grafana + cloudflared) to the monitoring VM.
# Called by CI (validate-infra.yml) or locally.
#
# Required env: GRAFANA_ADMIN_PASSWORD, CLOUDFLARE_TUNNEL_TOKEN
# Optional: GCP_PROJECT_ID, GCP_ZONE, MONITORING_INSTANCE, COMPOSE_ROOT,
#           SSH_USER, SSH_KEY_PATH, GRAFANA_SMTP_*

set -euo pipefail

export GCP_PROJECT_ID="${GCP_PROJECT_ID:-gmail-486411}"
GCP_ZONE="${GCP_ZONE:-us-east1-b}"
MONITORING_INSTANCE="${MONITORING_INSTANCE:-affordable-gadgets-production-monitoring}"
COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/affordable-gadgets}"
SSH_USER="${SSH_USER:-affordablegadgetske_gmail_com}"
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/ci_deploy_key}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD?GRAFANA_ADMIN_PASSWORD not set}"
CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN?CLOUDFLARE_TUNNEL_TOKEN not set}"
GRAFANA_SMTP_FROM="${GRAFANA_SMTP_FROM:-noreply@affordable-gadgetske.com}"
GRAFANA_SMTP_USER="${GRAFANA_SMTP_USER:-}"
GRAFANA_SMTP_PASSWORD="${GRAFANA_SMTP_PASSWORD:-}"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand='gcloud compute start-iap-tunnel $MONITORING_INSTANCE 22 --listen-on-stdin --project=$GCP_PROJECT_ID --zone=$GCP_ZONE' -i $SSH_KEY_PATH"

ssh_cmd() {
  ssh $SSH_OPTS "$SSH_USER@127.0.0.1" "$@"
}

# ── create directories ───────────────────────────────────────────────────────
ssh_cmd "mkdir -p $COMPOSE_ROOT/monitoring/prometheus $COMPOSE_ROOT/monitoring/grafana/datasources $COMPOSE_ROOT/monitoring/grafana/dashboards $COMPOSE_ROOT/monitoring/tunnel"

# ── render configs via Python ─────────────────────────────────────────────────
DEPLOY_DIR="$(cd "$(dirname "$0")/../deploy/ansible" && pwd)"
WORK_DIR=$(mktemp -d)
trap 'rm -rf $WORK_DIR' EXIT

python3 "$DEPLOY_DIR/../scripts/render_monitoring_templates.py" \
  "$DEPLOY_DIR/roles/monitoring_compose/templates" \
  "$WORK_DIR" \
  "$COMPOSE_ROOT" \
  "$GCP_PROJECT_ID" \
  "$GRAFANA_ADMIN_PASSWORD" \
  "$GRAFANA_SMTP_USER" \
  "$GRAFANA_SMTP_PASSWORD" \
  "$GRAFANA_SMTP_FROM" \
  "$CLOUDFLARE_TUNNEL_TOKEN"

# ── copy files to VM ─────────────────────────────────────────────────────────
scp $SSH_OPTS "$WORK_DIR/prometheus.yml"                "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/prometheus/prometheus.yml"
scp $SSH_OPTS "$WORK_DIR/grafana.env"                   "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana.env"
scp $SSH_OPTS "$WORK_DIR/tunnel.env"                    "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/tunnel/tunnel.env"
scp $SSH_OPTS "$WORK_DIR/docker-compose.monitoring.yml" "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/docker-compose.monitoring.yml"
scp $SSH_OPTS "$WORK_DIR/docker-compose.tunnel.yml"     "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/docker-compose.tunnel.yml"
scp $SSH_OPTS "$WORK_DIR/datasource.yml"                "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/datasources/datasource.yml"
scp $SSH_OPTS "$WORK_DIR/dashboards.yml"                "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/dashboards/dashboards.yml"
scp $SSH_OPTS "$WORK_DIR/alerts.yml"                    "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/prometheus/alerts.yml"
scp $SSH_OPTS "$WORK_DIR/django-dashboard.json"         "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/dashboards/django-dashboard.json"
scp $SSH_OPTS "$WORK_DIR/executive-kpi-dashboard.json"  "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/dashboards/executive-kpi-dashboard.json"

# ── restart containers ───────────────────────────────────────────────────────
ssh_cmd "docker compose -f $COMPOSE_ROOT/docker-compose.monitoring.yml --env-file $COMPOSE_ROOT/monitoring/grafana.env up -d --remove-orphans"
ssh_cmd "docker compose -f $COMPOSE_ROOT/docker-compose.tunnel.yml --env-file $COMPOSE_ROOT/monitoring/tunnel/tunnel.env up -d"

echo "✓ Monitoring stack deployed successfully"
