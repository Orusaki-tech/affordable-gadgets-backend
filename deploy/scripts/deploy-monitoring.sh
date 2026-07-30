#!/usr/bin/env bash
# Deploy monitoring stack to AWS monitoring EC2 via SSM (no gcloud IAP).
#
# Required env:
#   GRAFANA_ADMIN_PASSWORD
#   DJANGO_ADMIN_PASSWORD or DJANGO_API_TOKEN
#
# Optional:
#   AWS_REGION (default eu-north-1)
#   MONITORING_INSTANCE_ID (from terraform output)
#   API_PRIVATE_IP (for prometheus scrape target)
#   DEPLOY_TUNNEL_ON_MONITORING=0 (default; tunnel runs on API EC2)
#   GRAFANA_RENDERER_ENABLED=0 (default; saves RAM on t3.small)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deploy/terraform"
DEPLOY_DIR="$REPO_ROOT/deploy/ansible"
COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/affordable-gadgets}"
RENDERER_SCRIPT="$REPO_ROOT/scripts/render_monitoring_templates.py"
WATCHDOG_SCRIPT="$SCRIPT_DIR/monitoring-watchdog.sh"

AWS_REGION="${AWS_REGION:-eu-north-1}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD?GRAFANA_ADMIN_PASSWORD not set}"
CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"
DJANGO_ADMIN_PASSWORD="${DJANGO_ADMIN_PASSWORD:-}"
DJANGO_API_TOKEN="${DJANGO_API_TOKEN:-}"
DEPLOY_TUNNEL_ON_MONITORING="${DEPLOY_TUNNEL_ON_MONITORING:-0}"
GRAFANA_RENDERER_ENABLED="${GRAFANA_RENDERER_ENABLED:-0}"
export DEPLOY_TUNNEL_ON_MONITORING GRAFANA_RENDERER_ENABLED

if [[ -z "${MONITORING_INSTANCE_ID:-}" ]] && [[ -d "$TF_DIR" ]]; then
  MONITORING_INSTANCE_ID="$(terraform -chdir="$TF_DIR" output -raw monitoring_instance_id 2>/dev/null || true)"
fi
MONITORING_INSTANCE_ID="${MONITORING_INSTANCE_ID:?Set MONITORING_INSTANCE_ID or run terraform apply first}"

if [[ -z "${API_PRIVATE_IP:-}" ]] && [[ -d "$TF_DIR" ]]; then
  API_PRIVATE_IP="$(terraform -chdir="$TF_DIR" output -raw api_private_ip 2>/dev/null || true)"
fi
API_PRIVATE_IP="${API_PRIVATE_IP:-127.0.0.1}"

if [[ -z "${MONITORING_PRIVATE_IP:-}" ]] && [[ -d "$TF_DIR" ]]; then
  MONITORING_PRIVATE_IP="$(terraform -chdir="$TF_DIR" output -raw monitoring_private_ip 2>/dev/null || true)"
fi
MONITORING_PRIVATE_IP="${MONITORING_PRIVATE_IP:-}"

if [[ "$DEPLOY_TUNNEL_ON_MONITORING" == "1" && -z "$CLOUDFLARE_TUNNEL_TOKEN" ]]; then
  echo "CLOUDFLARE_TUNNEL_TOKEN required when DEPLOY_TUNNEL_ON_MONITORING=1" >&2
  exit 1
fi

ssm_run() {
  local cmd="$1"
  local params_file cmd_id status
  params_file=$(mktemp)
  python3 -c 'import json,sys; json.dump({"commands": [sys.argv[1]]}, open(sys.argv[2], "w"))' "$cmd" "$params_file"
  cmd_id=$(aws ssm send-command \
    --region "$AWS_REGION" \
    --instance-ids "$MONITORING_INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --comment "deploy-monitoring" \
    --parameters "file://$params_file" \
    --timeout-seconds 3600 \
    --query 'Command.CommandId' --output text)
  rm -f "$params_file"
  echo "→ SSM command $cmd_id"
  for _ in $(seq 1 90); do
    status=$(aws ssm get-command-invocation \
      --region "$AWS_REGION" \
      --command-id "$cmd_id" \
      --instance-id "$MONITORING_INSTANCE_ID" \
      --query 'Status' --output text 2>/dev/null || echo Pending)
    if [[ "$status" == "Success" ]]; then
      return 0
    fi
    if [[ "$status" == "Failed" || "$status" == "Cancelled" ]]; then
      aws ssm get-command-invocation \
        --region "$AWS_REGION" \
        --command-id "$cmd_id" \
        --instance-id "$MONITORING_INSTANCE_ID" \
        --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
      return 1
    fi
    sleep 10
  done
  echo "SSM command timed out: $cmd_id" >&2
  return 1
}

echo "→ Checking API health..."
API_TOKEN=""
if [[ -n "$DJANGO_ADMIN_PASSWORD" ]]; then
  for i in 1 2 3; do
    RESP=$(curl -s --show-error --fail \
      -X POST "https://api.affordable-gadgetske.com/api/auth/token/login/" \
      -H "Content-Type: application/json" \
      -d "{\"username\":\"admin\",\"password\":\"$DJANGO_ADMIN_PASSWORD\"}" 2>&1) \
      && API_TOKEN=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null) \
      && [[ -n "$API_TOKEN" ]] && break
    echo "  Token fetch attempt $i failed, retrying..."
    sleep 5
  done
fi
API_TOKEN="${API_TOKEN:-$DJANGO_API_TOKEN}"
if [[ -z "$API_TOKEN" ]]; then
  echo "ERROR: No Django API token. Set DJANGO_API_TOKEN or DJANGO_ADMIN_PASSWORD." >&2
  exit 1
fi
if [[ "$API_TOKEN" == "placeholder" ]]; then
  echo "ERROR: Refusing to deploy monitoring with placeholder API token." >&2
  exit 1
fi

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

python3 "$RENDERER_SCRIPT" \
  "$DEPLOY_DIR/roles/monitoring_compose/templates" \
  "$WORK_DIR" \
  "$COMPOSE_ROOT" \
  "aws" \
  "$GRAFANA_ADMIN_PASSWORD" \
  "${GRAFANA_SMTP_USER:-}" \
  "${GRAFANA_SMTP_PASSWORD:-}" \
  "${GRAFANA_SMTP_FROM:-noreply@affordable-gadgetske.com}" \
  "${CLOUDFLARE_TUNNEL_TOKEN:-placeholder}" \
  "$API_TOKEN" \
  "${API_PRIVATE_IP}:8000" \
  "production"

sed -i.bak "s|127.0.0.1:8000|${API_PRIVATE_IP}:8000|g" "$WORK_DIR/prometheus.yml" 2>/dev/null || true

BUCKET="${AWS_DEPLOY_CONFIG_BUCKET:-}"
if [[ -z "$BUCKET" ]] && [[ -d "$TF_DIR" ]]; then
  BUCKET="$(terraform -chdir="$TF_DIR" output -raw deploy_config_bucket 2>/dev/null || true)"
fi

if [[ -n "$BUCKET" ]]; then
  echo "→ Uploading monitoring configs to s3://$BUCKET/production/monitoring/"
  aws s3 cp "$WORK_DIR/prometheus.yml" "s3://$BUCKET/production/monitoring/monitoring/prometheus/prometheus.yml"
  aws s3 cp "$WORK_DIR/grafana.env" "s3://$BUCKET/production/monitoring/monitoring/grafana.env"
  aws s3 cp "$WORK_DIR/docker-compose.monitoring.yml" "s3://$BUCKET/production/monitoring/docker-compose.monitoring.yml"
  aws s3 cp "$WORK_DIR/datasource.yml" "s3://$BUCKET/production/monitoring/monitoring/grafana/datasources/datasource.yml"
  aws s3 cp "$DEPLOY_DIR/roles/monitoring_compose/files/dashboards.yml" "s3://$BUCKET/production/monitoring/monitoring/grafana/dashboards/dashboards.yml"
  aws s3 cp "$DEPLOY_DIR/roles/monitoring_compose/files/alerts.yml" "s3://$BUCKET/production/monitoring/monitoring/prometheus/alerts.yml"
  aws s3 cp "$WATCHDOG_SCRIPT" "s3://$BUCKET/production/monitoring/scripts/monitoring-watchdog.sh"
  if [[ "$DEPLOY_TUNNEL_ON_MONITORING" == "1" ]]; then
    aws s3 cp "$WORK_DIR/tunnel.env" "s3://$BUCKET/production/monitoring/monitoring/tunnel/tunnel.env"
    aws s3 cp "$WORK_DIR/docker-compose.tunnel.yml" "s3://$BUCKET/production/monitoring/docker-compose.tunnel.yml"
  fi
  for dash in django-dashboard executive-kpi-dashboard marketing-funnel daily-performance-dashboard; do
    aws s3 cp "$DEPLOY_DIR/roles/monitoring_compose/files/${dash}.json" \
      "s3://$BUCKET/production/monitoring/monitoring/grafana/dashboards/${dash}.json" 2>/dev/null || true
  done
fi

REMOTE_SCRIPT=$(cat <<EOF
set -eu
if ! docker compose version >/dev/null 2>&1; then
  COMPOSE_VERSION=v2.32.4
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/\${COMPOSE_VERSION}/docker-compose-linux-\$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
COMPOSE_ROOT="$COMPOSE_ROOT"
mkdir -p "\$COMPOSE_ROOT/monitoring/prometheus" "\$COMPOSE_ROOT/monitoring/grafana/datasources" "\$COMPOSE_ROOT/monitoring/grafana/dashboards" "\$COMPOSE_ROOT/scripts"
if [ -n "$BUCKET" ]; then
  aws s3 sync "s3://$BUCKET/production/monitoring/" "\$COMPOSE_ROOT/"
fi
if [ -f "\$COMPOSE_ROOT/grafana.env" ] && [ ! -f "\$COMPOSE_ROOT/monitoring/grafana.env" ]; then
  mv "\$COMPOSE_ROOT/grafana.env" "\$COMPOSE_ROOT/monitoring/grafana.env"
fi
if [ -d "\$COMPOSE_ROOT/grafana" ] && [ ! -d "\$COMPOSE_ROOT/monitoring/grafana/datasources" ]; then
  mkdir -p "\$COMPOSE_ROOT/monitoring/grafana"
  cp -a "\$COMPOSE_ROOT/grafana/." "\$COMPOSE_ROOT/monitoring/grafana/"
fi
if [ -d "\$COMPOSE_ROOT/prometheus" ] && [ ! -f "\$COMPOSE_ROOT/monitoring/prometheus/prometheus.yml" ]; then
  mkdir -p "\$COMPOSE_ROOT/monitoring/prometheus"
  cp -a "\$COMPOSE_ROOT/prometheus/." "\$COMPOSE_ROOT/monitoring/prometheus/"
fi
# 2 GB swap if missing
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -w vm.swappiness=10 2>/dev/null || true
# Install on-host watchdog
if [ -f "\$COMPOSE_ROOT/scripts/monitoring-watchdog.sh" ]; then
  chmod +x "\$COMPOSE_ROOT/scripts/monitoring-watchdog.sh"
  if [ ! -f /etc/systemd/system/ag-monitoring-watchdog.timer ]; then
    cat >/etc/systemd/system/ag-monitoring-watchdog.service <<'WUNIT'
[Unit]
Description=Monitoring stack health watchdog
[Service]
Type=oneshot
Environment=COMPOSE_ROOT=/opt/affordable-gadgets
ExecStart=/opt/affordable-gadgets/scripts/monitoring-watchdog.sh
WUNIT
    cat >/etc/systemd/system/ag-monitoring-watchdog.timer <<'WUNIT'
[Unit]
Description=Run monitoring watchdog every 2 minutes
[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
Persistent=true
[Install]
WantedBy=timers.target
WUNIT
    systemctl daemon-reload
    systemctl enable --now ag-monitoring-watchdog.timer
  fi
fi
docker rm -f ag-grafana ag-prometheus ag-grafana-renderer ag-cloudflared 2>/dev/null || true
docker compose -f "\$COMPOSE_ROOT/docker-compose.monitoring.yml" --env-file "\$COMPOSE_ROOT/monitoring/grafana.env" up -d --remove-orphans
if [ "$DEPLOY_TUNNEL_ON_MONITORING" = "1" ]; then
  docker compose -f "\$COMPOSE_ROOT/docker-compose.tunnel.yml" --env-file "\$COMPOSE_ROOT/monitoring/tunnel/tunnel.env" up -d
else
  docker rm -f ag-cloudflared 2>/dev/null || true
fi
for i in 1 2 3 4 5 6; do
  curl -sf http://localhost:3000/login >/dev/null && echo Grafana OK && break
  sleep 10
done
if ! curl -sf http://localhost:3000/login >/dev/null; then
  echo "Grafana health check failed"
  exit 1
fi
# Verify Infinity datasource can reach Django over VPC (same path as Prometheus)
HEALTH_JSON=\$(curl -sf --max-time 15 \\
  -H "Authorization: Token ${API_TOKEN}" \\
  "http://${API_PRIVATE_IP}:8000/api/inventory/analytics/datasource-health/" \\
  || echo "")
if ! echo "\$HEALTH_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('summary',{}).get('status')=='ok'; assert d.get('summary',{}).get('grafana_token_valid')=='true'"; then
  echo "Datasource health check failed (VPC path or token invalid)"
  echo "\$HEALTH_JSON"
  exit 1
fi
echo "Datasource health OK"
exit 0
EOF
)

ssm_run "$REMOTE_SCRIPT"

echo "✓ Monitoring deployed on $MONITORING_INSTANCE_ID"
echo "  Cloudflare tunnel runs on API EC2 (no dashboard change needed — grafana-proxy forwards :3000)."
echo "    api.affordable-gadgetske.com → http://localhost:8000"
echo "    grafana.affordable-gadgetske.com → http://localhost:3000 (socat → monitoring Grafana)"
