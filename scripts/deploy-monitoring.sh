#!/usr/bin/env bash
# Deploy monitoring stack (Prometheus + Grafana + cloudflared) to the monitoring VM.
# Called by CI (validate-infra.yml) or locally.
#
# Reads from environment / GitHub secrets:
#   GCP_PROJECT_ID          — (default gmail-486411)
#   GRAFANA_ADMIN_PASSWORD  — from vault (production.vault.yml)
#   CLOUDFLARE_TUNNEL_TOKEN — from vault (production.vault.yml)
#   COMPOSE_ROOT            — (default /opt/affordable-gadgets)
#   SSH_USER                — (default affordablegadgetske_gmail_com)
#   SSH_KEY_PATH            — (default ~/.ssh/ci_deploy_key)

set -euo pipefail

GCP_PROJECT_ID="${GCP_PROJECT_ID:-gmail-486411}"
GCP_ZONE="${GCP_ZONE:-us-east1-b}"
MONITORING_INSTANCE="${MONITORING_INSTANCE:-affordable-gadgets-production-monitoring}"
COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/affordable-gadgets}"
SSH_USER="${SSH_USER:-affordablegadgetske_gmail_com}"
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/ci_deploy_key}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD?GRAFANA_ADMIN_PASSWORD not set}"
CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN?CLOUDFLARE_TUNNEL_TOKEN not set}"

# ── helpers ──────────────────────────────────────────────────────────────────
ssh_cmd() {
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ProxyCommand="gcloud compute start-iap-tunnel $MONITORING_INSTANCE 22 --listen-on-stdin --project=$GCP_PROJECT_ID --zone=$GCP_ZONE" \
      -i "$SSH_KEY_PATH" \
      "$SSH_USER@127.0.0.1" "$@"
}

scp_cmd() {
  scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ProxyCommand="gcloud compute start-iap-tunnel $MONITORING_INSTANCE 22 --listen-on-stdin --project=$GCP_PROJECT_ID --zone=$GCP_ZONE" \
      -i "$SSH_KEY_PATH" \
      "$@"
}

# ── create directories ───────────────────────────────────────────────────────
ssh_cmd "mkdir -p $COMPOSE_ROOT/monitoring/prometheus $COMPOSE_ROOT/monitoring/grafana/datasources $COMPOSE_ROOT/monitoring/grafana/dashboards $COMPOSE_ROOT/monitoring/tunnel"

# ── render configs from J2 templates ─────────────────────────────────────────
DEPLOY_DIR="$(cd "$(dirname "$0")/../deploy/ansible" && pwd)"
WORK_DIR=$(mktemp -d)
trap 'rm -rf $WORK_DIR' EXIT

# prometheus.yml
sed -e "s|{{ gcp_project_id }}|$GCP_PROJECT_ID|g" \
    "$DEPLOY_DIR/roles/monitoring_compose/templates/prometheus.yml.j2" \
    > "$WORK_DIR/prometheus.yml"

# grafana.env
GRAFANA_SMTP_FROM="${GRAFANA_SMTP_FROM:-noreply@affordable-gadgetske.com}"
GRAFANA_SMTP_USER="${GRAFANA_SMTP_USER:-}"
GRAFANA_SMTP_PASSWORD="${GRAFANA_SMTP_PASSWORD:-}"
sed -e "s|{{ grafana_admin_password }}|$GRAFANA_ADMIN_PASSWORD|g" \
    -e "s|{{ grafana_smtp_user | default('') }}|$GRAFANA_SMTP_USER|g" \
    -e "s|{{ grafana_smtp_password | default('') }}|$GRAFANA_SMTP_PASSWORD|g" \
    -e "s|{{ grafana_smtp_from | default('noreply@affordable-gadgetske.com') }}|$GRAFANA_SMTP_FROM|g" \
    "$DEPLOY_DIR/roles/monitoring_compose/templates/grafana.env.j2" \
    > "$WORK_DIR/grafana.env"

# tunnel.env
echo "TUNNEL_TOKEN=$CLOUDFLARE_TUNNEL_TOKEN" > "$WORK_DIR/tunnel.env"

# compose files
sed -e "s|{{ compose_root }}|$COMPOSE_ROOT|g" \
    "$DEPLOY_DIR/roles/monitoring_compose/templates/docker-compose.monitoring.yml.j2" \
    > "$WORK_DIR/docker-compose.monitoring.yml"

sed -e "s|{{ compose_root }}|$COMPOSE_ROOT|g" \
    "$DEPLOY_DIR/roles/monitoring_compose/templates/tunnel-compose.yml.j2" \
    > "$WORK_DIR/docker-compose.tunnel.yml"

# static files
cp "$DEPLOY_DIR/roles/monitoring_compose/files/datasource.yml"     "$WORK_DIR/"
cp "$DEPLOY_DIR/roles/monitoring_compose/files/dashboards.yml"     "$WORK_DIR/"
cp "$DEPLOY_DIR/roles/monitoring_compose/files/alerts.yml"         "$WORK_DIR/"
cp "$DEPLOY_DIR/roles/monitoring_compose/files/django-dashboard.json"        "$WORK_DIR/"
cp "$DEPLOY_DIR/roles/monitoring_compose/files/executive-kpi-dashboard.json" "$WORK_DIR/"

# ── copy files to VM ─────────────────────────────────────────────────────────
scp_cmd "$WORK_DIR/prometheus.yml"                "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/prometheus/prometheus.yml"
scp_cmd "$WORK_DIR/grafana.env"                   "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana.env"
scp_cmd "$WORK_DIR/tunnel.env"                    "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/tunnel/tunnel.env"
scp_cmd "$WORK_DIR/docker-compose.monitoring.yml" "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/docker-compose.monitoring.yml"
scp_cmd "$WORK_DIR/docker-compose.tunnel.yml"     "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/docker-compose.tunnel.yml"
scp_cmd "$WORK_DIR/datasource.yml"                "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/datasources/datasource.yml"
scp_cmd "$WORK_DIR/dashboards.yml"                "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/dashboards/dashboards.yml"
scp_cmd "$WORK_DIR/alerts.yml"                    "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/prometheus/alerts.yml"
scp_cmd "$WORK_DIR/django-dashboard.json"         "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/dashboards/django-dashboard.json"
scp_cmd "$WORK_DIR/executive-kpi-dashboard.json"  "$SSH_USER@127.0.0.1:$COMPOSE_ROOT/monitoring/grafana/dashboards/executive-kpi-dashboard.json"

# ── restart containers ───────────────────────────────────────────────────────
ssh_cmd "docker compose -f $COMPOSE_ROOT/docker-compose.monitoring.yml --env-file $COMPOSE_ROOT/monitoring/grafana.env up -d --remove-orphans"
ssh_cmd "docker compose -f $COMPOSE_ROOT/docker-compose.tunnel.yml --env-file $COMPOSE_ROOT/monitoring/tunnel/tunnel.env up -d"

echo "✓ Monitoring stack deployed successfully"
