#!/usr/bin/env bash
# Deploy monitoring stack (Prometheus + Grafana + cloudflared) to the monitoring VM.
# Called by CI (validate-infra.yml) or locally.
#
# Required env: GRAFANA_ADMIN_PASSWORD, CLOUDFLARE_TUNNEL_TOKEN, DJANGO_ADMIN_PASSWORD
# Optional: GCP_PROJECT_ID, GCP_ZONE, MONITORING_INSTANCE, COMPOSE_ROOT,
#           SSH_USER, SSH_KEY_PATH, GRAFANA_SMTP_*

set -euo pipefail

export GCP_PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo project-07850c05-c54d-486b-80a)}"
GCP_ZONE="${GCP_ZONE:-us-east1-b}"
MONITORING_INSTANCE="${MONITORING_INSTANCE:-affordable-gadgets-production-monitoring}"
COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/affordable-gadgets}"
SSH_USER="${SSH_USER:-$(gcloud compute os-login describe-profile --format='value(posixAccounts[0].username)' 2>/dev/null || echo affordablegadgetske_gmail_com)}"
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/ci_deploy_key}"
# Prefer docker compose (plugin) over standalone docker-compose binary
if command -v docker-compose &>/dev/null; then
  DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker-compose}"
else
  DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
fi
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD?GRAFANA_ADMIN_PASSWORD not set}"
CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"
DJANGO_ADMIN_PASSWORD="${DJANGO_ADMIN_PASSWORD:-}"
DJANGO_API_TOKEN="${DJANGO_API_TOKEN:-}"
GRAFANA_SMTP_FROM="${GRAFANA_SMTP_FROM:-noreply@affordable-gadgetske.com}"
GRAFANA_SMTP_USER="${GRAFANA_SMTP_USER:-}"
GRAFANA_SMTP_PASSWORD="${GRAFANA_SMTP_PASSWORD:-}"

SSH_OPTS=(
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o ProxyCommand='gcloud compute start-iap-tunnel '"$MONITORING_INSTANCE"' 22 --listen-on-stdin --project='"$GCP_PROJECT_ID"' --zone='"$GCP_ZONE"'' 
  -i "$SSH_KEY_PATH"
)

ssh_cmd() {
  ssh "${SSH_OPTS[@]}" "$SSH_USER@127.0.0.1" "$@"
}

sudo_cmd() {
  ssh "${SSH_OPTS[@]}" "$SSH_USER@127.0.0.1" "sudo bash -c '$*'"
}

# ── health check: confirm API is serving before fetching token ────────────────
echo "→ Checking API health..."
for i in 1 2 3; do
  if curl -sf --max-time 10 "https://api.affordable-gadgetske.com/metrics/" > /dev/null 2>&1; then
    echo "  API is healthy"
    break
  fi
  echo "  Attempt $i failed, retrying in 10s..."
  [ "$i" -lt 3 ] && sleep 10
done

# ── fetch API token for Grafana datasource ────────────────────────────────────
if [[ -n "$DJANGO_API_TOKEN" ]]; then
  echo "→ Using provided DJANGO_API_TOKEN"
  API_TOKEN="$DJANGO_API_TOKEN"
else
  if [[ -z "$DJANGO_ADMIN_PASSWORD" ]]; then
    echo "DJANGO_ADMIN_PASSWORD or DJANGO_API_TOKEN must be set" >&2
    exit 1
  fi
  echo "→ Fetching API token from admin password..."
  API_TOKEN=""
  for i in 1 2 3; do
    RESP=$(curl -s --show-error --fail \
      -X POST "https://api.affordable-gadgetske.com/api/auth/token/login/" \
      -H "Content-Type: application/json" \
      -d "{\"username\":\"admin\",\"password\":\"$DJANGO_ADMIN_PASSWORD\"}" 2>&1) \
      && API_TOKEN=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null) \
      && break
    echo "  Attempt $i failed (${RESP:0:200}), retrying in 10s..."
    [ "$i" -lt 3 ] && sleep 10
  done
  if [[ -z "$API_TOKEN" ]]; then
    echo "ERROR: Could not obtain API token after 3 attempts." >&2
    echo "  - Check that DJANGO_ADMIN_PASSWORD matches the production admin password." >&2
    echo "  - Ensure the admin user has is_staff=True and an Admin profile (auto-created on login)." >&2
    echo "  - Alternatively, set DJANGO_API_TOKEN to a static DRF token for a staff user." >&2
    exit 1
  fi
fi

TMP_DIR="/tmp/monitoring-deploy"

# ── clean temp dir on VM ─────────────────────────────────────────────────────
ssh_cmd "rm -rf $TMP_DIR && mkdir -p $TMP_DIR"

# ── render configs via Python ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR/../deploy/ansible"
WORK_DIR=$(mktemp -d)
trap 'rm -rf $WORK_DIR' EXIT

if [[ "${DEPLOY_TUNNEL_ON_MONITORING:-0}" == "1" && -z "$CLOUDFLARE_TUNNEL_TOKEN" ]]; then
  echo "CLOUDFLARE_TUNNEL_TOKEN required when DEPLOY_TUNNEL_ON_MONITORING=1" >&2
  exit 1
fi

python3 "$SCRIPT_DIR/render_monitoring_templates.py" \
  "$DEPLOY_DIR/roles/monitoring_compose/templates" \
  "$WORK_DIR" \
  "$COMPOSE_ROOT" \
  "$GCP_PROJECT_ID" \
  "$GRAFANA_ADMIN_PASSWORD" \
  "$GRAFANA_SMTP_USER" \
  "$GRAFANA_SMTP_PASSWORD" \
  "$GRAFANA_SMTP_FROM" \
  "${CLOUDFLARE_TUNNEL_TOKEN:-placeholder}" \
  "$API_TOKEN"

# ── copy files to temp dir on VM ──────────────────────────────────────────────
scp "${SSH_OPTS[@]}" "$WORK_DIR/prometheus.yml"                "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/grafana.env"                   "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/tunnel.env"                    "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/docker-compose.monitoring.yml" "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/docker-compose.tunnel.yml"     "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/datasource.yml"                "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/dashboards.yml"                "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/alerts.yml"                    "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/django-dashboard.json"         "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/executive-kpi-dashboard.json"  "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/daily-performance-dashboard.json" "$SSH_USER@127.0.0.1:$TMP_DIR/"
scp "${SSH_OPTS[@]}" "$WORK_DIR/marketing-funnel.json"              "$SSH_USER@127.0.0.1:$TMP_DIR/"

# ── move files to compose_root via sudo ───────────────────────────────────────
sudo_cmd "mkdir -p $COMPOSE_ROOT/monitoring/prometheus $COMPOSE_ROOT/monitoring/grafana/datasources $COMPOSE_ROOT/monitoring/grafana/dashboards $COMPOSE_ROOT/monitoring/tunnel"
sudo_cmd "cp $TMP_DIR/prometheus.yml                $COMPOSE_ROOT/monitoring/prometheus/prometheus.yml"
sudo_cmd "cp $TMP_DIR/grafana.env                   $COMPOSE_ROOT/monitoring/grafana.env"
sudo_cmd "cp $TMP_DIR/tunnel.env                    $COMPOSE_ROOT/monitoring/tunnel/tunnel.env"
sudo_cmd "cp $TMP_DIR/docker-compose.monitoring.yml $COMPOSE_ROOT/docker-compose.monitoring.yml"
sudo_cmd "cp $TMP_DIR/docker-compose.tunnel.yml     $COMPOSE_ROOT/docker-compose.tunnel.yml"
sudo_cmd "cp $TMP_DIR/datasource.yml                $COMPOSE_ROOT/monitoring/grafana/datasources/datasource.yml"
sudo_cmd "cp $TMP_DIR/dashboards.yml                $COMPOSE_ROOT/monitoring/grafana/dashboards/dashboards.yml"
sudo_cmd "cp $TMP_DIR/alerts.yml                    $COMPOSE_ROOT/monitoring/prometheus/alerts.yml"
sudo_cmd "cp $TMP_DIR/django-dashboard.json         $COMPOSE_ROOT/monitoring/grafana/dashboards/django-dashboard.json"
sudo_cmd "cp $TMP_DIR/executive-kpi-dashboard.json  $COMPOSE_ROOT/monitoring/grafana/dashboards/executive-kpi-dashboard.json"
sudo_cmd "cp $TMP_DIR/daily-performance-dashboard.json  $COMPOSE_ROOT/monitoring/grafana/dashboards/daily-performance-dashboard.json"
sudo_cmd "cp $TMP_DIR/marketing-funnel.json              $COMPOSE_ROOT/monitoring/grafana/dashboards/marketing-funnel.json"

# ── clean up temp dir ────────────────────────────────────────────────────────
ssh_cmd "rm -rf $TMP_DIR"

# ── remove incompatible plugins from data volume ─────────────────────────────
# These plugins require react/jsx-runtime (Grafana 13+) and break on 11.x.
sudo_cmd "docker run --rm -v ${COMPOSE_ROOT}/grafana_data:/var/lib/grafana busybox rm -rf \
  /var/lib/grafana/plugins/grafana-pyroscope-app \
  /var/lib/grafana/plugins/grafana-exploretraces-app \
  /var/lib/grafana/plugins/grafana-lokiexplore-app" 2>/dev/null || true

# ── restart containers ───────────────────────────────────────────────────────
sudo_cmd "$DOCKER_COMPOSE -f $COMPOSE_ROOT/docker-compose.monitoring.yml --env-file $COMPOSE_ROOT/monitoring/grafana.env up -d --remove-orphans"
# Force Grafana restart so it picks up provisioning file changes.
sudo_cmd "$DOCKER_COMPOSE -f $COMPOSE_ROOT/docker-compose.monitoring.yml --env-file $COMPOSE_ROOT/monitoring/grafana.env restart grafana" || true

# Tunnel runs on affordable-gadgets-production-tunnel (not this VM).
if [[ "${DEPLOY_TUNNEL_ON_MONITORING:-0}" == "1" ]]; then
  sudo_cmd "$DOCKER_COMPOSE -f $COMPOSE_ROOT/docker-compose.tunnel.yml --env-file $COMPOSE_ROOT/monitoring/tunnel/tunnel.env up -d"
else
  echo "→ Skipping cloudflared (DEPLOY_TUNNEL_ON_MONITORING!=1); tunnel VM handles ingress"
fi

echo "✓ Monitoring stack deployed successfully"
