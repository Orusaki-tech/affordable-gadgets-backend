#!/usr/bin/env bash
# Deploy monitoring stack to AWS monitoring EC2 via SSM (no gcloud IAP).
#
# Required env:
#   GRAFANA_ADMIN_PASSWORD
#   CLOUDFLARE_TUNNEL_TOKEN (when DEPLOY_TUNNEL_ON_MONITORING=1)
#   DJANGO_ADMIN_PASSWORD or DJANGO_API_TOKEN
#
# Optional:
#   AWS_REGION (default eu-north-1)
#   MONITORING_INSTANCE_ID (from terraform output)
#   API_PRIVATE_IP (for prometheus scrape target)
#   DEPLOY_TUNNEL_ON_MONITORING=1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deploy/terraform"
DEPLOY_DIR="$REPO_ROOT/deploy/ansible"
COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/affordable-gadgets}"
RENDERER_SCRIPT="$REPO_ROOT/scripts/render_monitoring_templates.py"

AWS_REGION="${AWS_REGION:-eu-north-1}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD?GRAFANA_ADMIN_PASSWORD not set}"
CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"
DJANGO_ADMIN_PASSWORD="${DJANGO_ADMIN_PASSWORD:-}"
DJANGO_API_TOKEN="${DJANGO_API_TOKEN:-}"
DEPLOY_TUNNEL_ON_MONITORING="${DEPLOY_TUNNEL_ON_MONITORING:-1}"

if [[ -z "${MONITORING_INSTANCE_ID:-}" ]] && [[ -d "$TF_DIR" ]]; then
  MONITORING_INSTANCE_ID="$(terraform -chdir="$TF_DIR" output -raw monitoring_instance_id 2>/dev/null || true)"
fi
MONITORING_INSTANCE_ID="${MONITORING_INSTANCE_ID:?Set MONITORING_INSTANCE_ID or run terraform apply first}"

if [[ -z "${API_PRIVATE_IP:-}" ]] && [[ -d "$TF_DIR" ]]; then
  API_PRIVATE_IP="$(terraform -chdir="$TF_DIR" output -raw api_private_ip 2>/dev/null || true)"
fi
API_PRIVATE_IP="${API_PRIVATE_IP:-127.0.0.1}"

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
  echo "WARN: No Django API token; Grafana JSON panels may fail until API is up"
  API_TOKEN="placeholder"
fi

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# Render templates (prometheus uses API private IP via env override in rendered file)
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

# Legacy sed patch kept for GCP renders; no-op for AWS static prometheus.yml
sed -i.bak "s|127.0.0.1:8000|${API_PRIVATE_IP}:8000|g" "$WORK_DIR/prometheus.yml" 2>/dev/null || true

# Use AWS datasource (no Stackdriver)
cp "$DEPLOY_DIR/roles/monitoring_compose/files/datasource.yml" "$WORK_DIR/datasource.yml"

BUCKET="${AWS_DEPLOY_CONFIG_BUCKET:-}"
if [[ -z "$BUCKET" ]] && [[ -d "$TF_DIR" ]]; then
  BUCKET="$(terraform -chdir="$TF_DIR" output -raw deploy_config_bucket 2>/dev/null || true)"
fi

if [[ -n "$BUCKET" ]]; then
  echo "→ Uploading monitoring configs to s3://$BUCKET/production/monitoring/"
  aws s3 cp "$WORK_DIR/prometheus.yml" "s3://$BUCKET/production/monitoring/monitoring/prometheus/prometheus.yml"
  aws s3 cp "$WORK_DIR/grafana.env" "s3://$BUCKET/production/monitoring/monitoring/grafana.env"
  aws s3 cp "$WORK_DIR/tunnel.env" "s3://$BUCKET/production/monitoring/monitoring/tunnel/tunnel.env"
  aws s3 cp "$WORK_DIR/docker-compose.monitoring.yml" "s3://$BUCKET/production/monitoring/docker-compose.monitoring.yml"
  aws s3 cp "$WORK_DIR/docker-compose.tunnel.yml" "s3://$BUCKET/production/monitoring/docker-compose.tunnel.yml"
  aws s3 cp "$WORK_DIR/datasource.yml" "s3://$BUCKET/production/monitoring/monitoring/grafana/datasources/datasource.yml"
  aws s3 cp "$DEPLOY_DIR/roles/monitoring_compose/files/dashboards.yml" "s3://$BUCKET/production/monitoring/monitoring/grafana/dashboards/dashboards.yml"
  aws s3 cp "$DEPLOY_DIR/roles/monitoring_compose/files/alerts.yml" "s3://$BUCKET/production/monitoring/monitoring/prometheus/alerts.yml"
  for dash in django-dashboard executive-kpi-dashboard marketing-funnel daily-performance-dashboard; do
    aws s3 cp "$DEPLOY_DIR/roles/monitoring_compose/files/${dash}.json" \
      "s3://$BUCKET/production/monitoring/monitoring/grafana/dashboards/${dash}.json" 2>/dev/null || true
  done
fi

# Stage files on instance via SSM + base64 chunks would be heavy; use S3 sync on VM
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
mkdir -p "\$COMPOSE_ROOT/monitoring/prometheus" "\$COMPOSE_ROOT/monitoring/grafana/datasources" "\$COMPOSE_ROOT/monitoring/grafana/dashboards" "\$COMPOSE_ROOT/monitoring/tunnel"
if [ -n "$BUCKET" ]; then
  aws s3 sync "s3://$BUCKET/production/monitoring/" "\$COMPOSE_ROOT/"
fi
# Normalize legacy sync paths from earlier deploy attempts
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
if [ -f "\$COMPOSE_ROOT/tunnel/tunnel.env" ] && [ ! -f "\$COMPOSE_ROOT/monitoring/tunnel/tunnel.env" ]; then
  mkdir -p "\$COMPOSE_ROOT/monitoring/tunnel"
  cp "\$COMPOSE_ROOT/tunnel/tunnel.env" "\$COMPOSE_ROOT/monitoring/tunnel/tunnel.env"
fi
docker rm -f ag-grafana ag-prometheus ag-grafana-renderer ag-cloudflared 2>/dev/null || true
docker compose -f "\$COMPOSE_ROOT/docker-compose.monitoring.yml" --env-file "\$COMPOSE_ROOT/monitoring/grafana.env" up -d --remove-orphans
if [ "$DEPLOY_TUNNEL_ON_MONITORING" = "1" ]; then
  docker compose -f "\$COMPOSE_ROOT/docker-compose.tunnel.yml" --env-file "\$COMPOSE_ROOT/monitoring/tunnel/tunnel.env" up -d
fi
for i in 1 2 3 4 5 6; do
  curl -sf http://localhost:3000/login >/dev/null && echo Grafana OK && exit 0
  sleep 10
done
echo "Grafana health check failed"
exit 1
EOF
)

ssm_run "$REMOTE_SCRIPT"

echo "✓ Monitoring deployed on $MONITORING_INSTANCE_ID"
echo "  Configure Cloudflare tunnel routes:"
echo "    api.affordable-gadgetske.com → http://${API_PRIVATE_IP}:8000"
echo "    grafana.affordable-gadgetske.com → http://localhost:3000"
