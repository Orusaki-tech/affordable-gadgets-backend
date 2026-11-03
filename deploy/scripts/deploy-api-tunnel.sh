#!/usr/bin/env bash
# Deploy Cloudflare tunnel on API EC2 (ingress for api + grafana hostnames).
# Run after terraform apply and before updating Cloudflare Zero Trust routes.
#
# Required env: CLOUDFLARE_TUNNEL_TOKEN, AWS_API_INSTANCE_ID (or terraform output)
# Uses ansible vault for token when run locally with vault configured.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ANSIBLE_DIR="$REPO_ROOT/deploy/ansible"

AWS_REGION="${AWS_REGION:-eu-north-1}"

if [[ -z "${API_INSTANCE_ID:-}" ]]; then
  API_INSTANCE_ID="$(terraform -chdir="$REPO_ROOT/deploy/terraform" output -raw api_instance_id 2>/dev/null || true)"
fi
API_INSTANCE_ID="${API_INSTANCE_ID:-${AWS_API_INSTANCE_ID:-}}"
API_INSTANCE_ID="${API_INSTANCE_ID:?Set API_INSTANCE_ID or AWS_API_INSTANCE_ID}"

if [[ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" && -f "$ANSIBLE_DIR/secrets/production.vault.yml" ]]; then
  echo "→ Rendering tunnel config via Ansible (vault)"
  cd "$ANSIBLE_DIR"
  if [[ -f vars/generated_from_terraform.yml ]]; then
    :
  else
    python3 "$REPO_ROOT/deploy/scripts/generate_ansible_vars.py" > vars/generated_from_terraform.yml
  fi
  VAULT_PASS="${ANSIBLE_VAULT_PASSWORD:-}"
  if [[ -z "$VAULT_PASS" && -f /tmp/vault-pass ]]; then
    VAULT_PASS="$(cat /tmp/vault-pass)"
  fi
  if [[ -z "$VAULT_PASS" ]]; then
    echo "Set ANSIBLE_VAULT_PASSWORD or create /tmp/vault-pass" >&2
    exit 1
  fi
  echo "$VAULT_PASS" > /tmp/vault-pass
  chmod 600 /tmp/vault-pass
  ansible-playbook playbooks/api.yml \
    --vault-password-file /tmp/vault-pass \
    -e aws_deploy_restart=true \
    -e deploy_tunnel_on_api=true
  rm -f /tmp/vault-pass
  echo "✓ API tunnel deployed via Ansible"
  "$SCRIPT_DIR/cloudflare-cutover.sh"
  exit 0
fi

CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:?CLOUDFLARE_TUNNEL_TOKEN not set}"

BUCKET="${AWS_DEPLOY_CONFIG_BUCKET:-}"
if [[ -z "$BUCKET" ]]; then
  BUCKET="$(terraform -chdir="$REPO_ROOT/deploy/terraform" output -raw deploy_config_bucket 2>/dev/null || true)"
fi
BUCKET="${BUCKET:?Set AWS_DEPLOY_CONFIG_BUCKET}"

COMPOSE_ROOT="/opt/affordable-gadgets"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

mkdir -p "$WORK_DIR/tunnel"
cat >"$WORK_DIR/tunnel/tunnel.env" <<EOF
CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
EOF
MON_IP=$(terraform -chdir="$REPO_ROOT/deploy/terraform" output -raw monitoring_private_ip 2>/dev/null || true)
MON_IP="${MON_IP:-${MONITORING_PRIVATE_IP:-10.0.1.248}}"

cat >"$WORK_DIR/docker-compose.tunnel.yml" <<EOF
services:
  grafana-proxy:
    image: alpine/socat
    container_name: ag-grafana-proxy
    restart: always
    network_mode: host
    command: TCP-LISTEN:3000,fork,reuseaddr TCP:${MON_IP}:3000

  cloudflared:
    image: cloudflare/cloudflared:2024.2.1
    container_name: ag-api-cloudflared
    restart: always
    network_mode: host
    depends_on:
      - grafana-proxy
    env_file:
      - ${COMPOSE_ROOT}/tunnel/tunnel.env
    environment:
      CLOUDFLARE_TUNNEL_TOKEN: \${CLOUDFLARE_TUNNEL_TOKEN}
    command: tunnel --no-autoupdate run --protocol http2 --token \${CLOUDFLARE_TUNNEL_TOKEN}
EOF

echo "→ Uploading tunnel config to s3://$BUCKET/production/api/"
aws s3 cp "$WORK_DIR/tunnel/tunnel.env" "s3://$BUCKET/production/api/tunnel/tunnel.env"
aws s3 cp "$WORK_DIR/docker-compose.tunnel.yml" "s3://$BUCKET/production/api/docker-compose.tunnel.yml"

echo "→ Starting tunnel on $API_INSTANCE_ID"
CMD_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$API_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "deploy-api-tunnel" \
  --parameters 'commands=["cd /opt/affordable-gadgets","aws s3 sync s3://'"$BUCKET"'/production/api/ .","docker rm -f ag-cloudflared ag-api-cloudflared 2>/dev/null || true","docker compose -f docker-compose.tunnel.yml --env-file tunnel/tunnel.env up -d","docker ps --filter name=ag-api-cloudflared"]' \
  --query 'Command.CommandId' --output text)

for _ in $(seq 1 24); do
  STATUS=$(aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$CMD_ID" \
    --instance-id "$API_INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo Pending)
  [[ "$STATUS" == "Success" ]] && break
  [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" ]] && exit 1
  sleep 5
done

aws ssm get-command-invocation \
  --region "$AWS_REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$API_INSTANCE_ID" \
  --query '[Status,StandardOutputContent]' --output text

echo "✓ API tunnel deployed"
"$SCRIPT_DIR/cloudflare-cutover.sh"
