#!/usr/bin/env bash
# Start Cloudflare Tunnel on the GCP VM (Docker Compose) to replace ngrok.
#
# Requirements:
# - You already created the tunnel in Cloudflare and configured a Public Hostname, e.g.:
#     api.affordable-gadgetske.com  ->  http://web:8000
# - Export the token in your terminal before running:
#     CLOUDFLARE_TUNNEL_TOKEN=... ./deploy/cloudflare-on-vm.sh
#
# What this script does:
# - Ensures the VM .env contains api.affordable-gadgetske.com in ALLOWED_HOSTS
# - Sets PESAPAL_IPN_URL to https://api.affordable-gadgetske.com/api/inventory/pesapal/ipn/ (overrideable)
# - Starts/restarts the cloudflared compose service on the VM
#
# Run from backend repo root: ./deploy/cloudflare-on-vm.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_DIR="/home/${REMOTE_USER}/affordable-gadgets-backend"

if [[ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
  echo "ERROR: CLOUDFLARE_TUNNEL_TOKEN is required."
  echo "  Export it and rerun:"
  echo "    CLOUDFLARE_TUNNEL_TOKEN=... ./deploy/cloudflare-on-vm.sh"
  exit 1
fi

PUBLIC_API_BASE_URL="${PUBLIC_API_BASE_URL:-https://api.affordable-gadgetske.com}"
PUBLIC_API_HOST="$(echo "${PUBLIC_API_BASE_URL}" | sed -E 's|https?://([^/]+).*|\\1|')"
PESAPAL_IPN_URL="${PESAPAL_IPN_URL:-${PUBLIC_API_BASE_URL%/}/api/inventory/pesapal/ipn/}"

cd "${TERRAFORM_DIR}"
INSTANCE_NAME="$(terraform output -raw instance_name 2>/dev/null)" || {
  echo "Run Terraform first (deploy-gcp.sh or terraform apply)."
  exit 1
}
ZONE="$(terraform output -raw zone)"
PROJECT_ID="$(terraform output -raw project_id 2>/dev/null)" || true

echo "==> VM: ${INSTANCE_NAME}"
echo "==> Using public API host: ${PUBLIC_API_HOST}"

GCLOUD_SSH=(gcloud compute ssh "${REMOTE_USER}@${INSTANCE_NAME}" --zone="${ZONE}")
[[ -n "${PROJECT_ID}" ]] && GCLOUD_SSH+=(--project="${PROJECT_ID}")
if [[ "${USE_IAP_TUNNEL:-0}" = "1" ]]; then
  GCLOUD_SSH+=(--tunnel-through-iap)
fi

# Update VM .env and restart cloudflared.
# Pass token via env var; do not print it.
"${GCLOUD_SSH[@]}" --command="
  set -e
  cd ${REMOTE_DIR}
  if [ ! -f .env ]; then
    echo 'ERROR: .env missing. Run ./deploy/deploy-gcp.sh from your laptop first.' >&2
    exit 1
  fi

  # Ensure ALLOWED_HOSTS includes the stable public API hostname.
  if ! grep -q \"${PUBLIC_API_HOST}\" .env 2>/dev/null; then
    sed -i 's/^ALLOWED_HOSTS=\\(.*\\)/ALLOWED_HOSTS=\\1,'\"${PUBLIC_API_HOST}\"'/' .env
  fi

  # Ensure PESAPAL_IPN_URL points at the stable HTTPS hostname (required for Pesapal callbacks).
  sed -i '/^PESAPAL_IPN_URL=/d' .env
  echo \"PESAPAL_IPN_URL=${PESAPAL_IPN_URL}\" >> .env

  # Reload environment variables into the running app container.
  # docker compose reads env_file only on container create, so we must recreate.
  if sudo docker compose version >/dev/null 2>&1; then
    sudo docker compose up -d --force-recreate web
  else
    sudo docker-compose up -d --force-recreate web
  fi

  # Start/update cloudflared tunnel container.
  export CLOUDFLARE_TUNNEL_TOKEN='${CLOUDFLARE_TUNNEL_TOKEN}'
  if sudo docker compose version >/dev/null 2>&1; then
    sudo -E docker compose up -d cloudflared
  else
    sudo -E docker-compose up -d cloudflared
  fi
"

echo ""
echo "==> Cloudflare tunnel service started on VM."
echo "Use this HTTPS URL in Vercel:"
echo "  ${PUBLIC_API_BASE_URL}"
echo ""
echo "Vercel env vars:"
echo "  Admin:     REACT_APP_API_BASE_URL=${PUBLIC_API_BASE_URL}/api/inventory"
echo "  Frontend:  NEXT_PUBLIC_API_URL=${PUBLIC_API_BASE_URL}"
echo ""

