#!/usr/bin/env bash
# Install ngrok on the GCP VM and start a tunnel to port 8000. Outputs the HTTPS URL
# for you to add to Vercel (e.g. REACT_APP_API_BASE_URL or NEXT_PUBLIC_API_URL).
# Run from backend repo root: ./deploy/ngrok-on-vm.sh
# Optional: set NGROK_AUTH_TOKEN (from https://dashboard.ngrok.com/get-started/your-authtoken) for a stable URL and no interstitial.
#
# To avoid typing your SSH key passphrase every time, run once in the same terminal:
#   eval $(ssh-agent -s) && ssh-add ~/.ssh/google_compute_engine
# Then run this script; it will use the agent and not prompt.
#
# Default user is ubuntu (matches deploy-gcp.sh and the VM image). Override with REMOTE_USER=youruser if needed.
# SSH uses direct connection (port 22) by default. Use IAP if needed: USE_IAP_TUNNEL=1 ./deploy/ngrok-on-vm.sh
# Run once so the script does not prompt for key passphrase: eval $(ssh-agent -s) && ssh-add ~/.ssh/google_compute_engine

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
# Ubuntu image + deploy-gcp.sh use "ubuntu"; default to ubuntu so key is added for the right user.
REMOTE_USER="${REMOTE_USER:-ubuntu}"

cd "${TERRAFORM_DIR}"
IP="$(terraform output -raw external_ip 2>/dev/null)" || { echo "Run Terraform first (deploy-gcp.sh or terraform apply)."; exit 1; }
ZONE="$(terraform output -raw zone)"
INSTANCE_NAME="$(terraform output -raw instance_name)"
PROJECT_ID="$(terraform output -raw project_id 2>/dev/null)" || true

echo "==> VM: ${INSTANCE_NAME}, IP: ${IP}"
echo "==> Installing ngrok and starting tunnel to port 8000..."

GCLOUD_SSH=(gcloud compute ssh "${REMOTE_USER}@${INSTANCE_NAME}" --zone="${ZONE}")
[[ -n "${PROJECT_ID}" ]] && GCLOUD_SSH+=(--project="${PROJECT_ID}")
# Use IAP only when requested (direct SSH works when port 22 is open and key is in agent).
if [[ "${USE_IAP_TUNNEL:-0}" = "1" ]]; then
  GCLOUD_SSH+=(--tunnel-through-iap)
fi

# Optional: pass authtoken so ngrok URL is stable and no interstitial (user sets NGROK_AUTH_TOKEN env)
NGROK_AUTH="${NGROK_AUTH_TOKEN:-}"

# Write remote script to a temp file, copy to VM, and run (avoids long --command and quoting issues)
REMOTE_SCRIPT=$(mktemp)
trap 'rm -f "${REMOTE_SCRIPT}"' EXIT
cat << REMOTEEOF > "${REMOTE_SCRIPT}"
set -e
if ! command -v ngrok &>/dev/null; then
  echo "Downloading ngrok..." 1>&2
  ( sudo curl -sL "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" -o /tmp/ngrok.tgz || sudo curl -sL "https://github.com/ngrok/ngrok/releases/latest/download/ngrok-v3-stable-linux-amd64.tgz" -o /tmp/ngrok.tgz ) && sudo tar xzf /tmp/ngrok.tgz -C /tmp && sudo mv /tmp/ngrok /usr/local/bin/ngrok && sudo chmod +x /usr/local/bin/ngrok
  sudo rm -f /tmp/ngrok.tgz
fi
if [ -n "${NGROK_AUTH}" ]; then
  ngrok config add-authtoken "${NGROK_AUTH}" 2>/dev/null || true
fi
pkill -f "ngrok http" 2>/dev/null || true
sleep 2
nohup ngrok http 8000 --log=stdout --log-level=error > /tmp/ngrok.log 2>&1 &
URL=""
for i in 1 2 3 4 5; do
  sleep 3
  URL=\$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tunnels = d.get('tunnels', [])
    if tunnels:
        print(tunnels[0].get('public_url', ''))
except Exception:
    pass
" 2>/dev/null || true)
  [ -n "\$URL" ] && break
done
if [ -z "\$URL" ]; then
  echo "Could not get ngrok URL. Ngrok requires a free authtoken." 1>&2
  echo "Get one at https://dashboard.ngrok.com/get-started/your-authtoken then run:" 1>&2
  echo "  NGROK_AUTH_TOKEN=your_token ./deploy/ngrok-on-vm.sh" 1>&2
  echo "Or check /tmp/ngrok.log on the VM." 1>&2
  exit 1
fi
echo "\$URL"
REMOTEEOF

echo ""
GCLOUD_SCP=(gcloud compute scp "${REMOTE_SCRIPT}" "${REMOTE_USER}@${INSTANCE_NAME}:/tmp/ngrok-setup.sh" --zone="${ZONE}")
[[ -n "${PROJECT_ID}" ]] && GCLOUD_SCP+=(--project="${PROJECT_ID}")
[[ "${USE_IAP_TUNNEL:-0}" = "1" ]] && GCLOUD_SCP+=(--tunnel-through-iap)
"${GCLOUD_SCP[@]}" -q 2>&1 || true

SSH_OUTPUT=$("${GCLOUD_SSH[@]}" --command="bash /tmp/ngrok-setup.sh" 2>&1) || true

# Extract URL (last line of SSH output that looks like https://)
# Use grep ... || true so missing match doesn't trigger set -e and hide the error output
NGROK_URL=$(echo "$SSH_OUTPUT" | grep -E '^https://' | tail -1) || true

if [[ -z "${NGROK_URL}" ]]; then
  echo "--- Remote command output (stdout + stderr) ---"
  echo "$SSH_OUTPUT"
  echo "---"
  echo ""
  echo "Failed to get ngrok URL. Ngrok's free tier requires an authtoken."
  echo "  1. Get a free token: https://dashboard.ngrok.com/get-started/your-authtoken"
  echo "  2. Run: NGROK_AUTH_TOKEN=your_token ./deploy/ngrok-on-vm.sh"
  echo "  3. Or SSH to the VM and run: ngrok http 8000  (after configuring ngrok config add-authtoken YOUR_TOKEN)"
  echo "  4. If key prompts: eval \$(ssh-agent -s) && ssh-add ~/.ssh/google_compute_engine  then run the script again"
  exit 1
fi

NGROK_HOST=$(echo "${NGROK_URL}" | sed -E 's|https?://([^/]+).*|\1|')
echo "==> Updating backend ALLOWED_HOSTS and CORS on VM to include ${NGROK_HOST}..."
"${GCLOUD_SSH[@]}" --command="
  cd /home/${REMOTE_USER}/affordable-gadgets-backend 2>/dev/null || true
  if [ -f .env ]; then
    if ! grep -q \"${NGROK_HOST}\" .env 2>/dev/null; then
      sed -i 's/^ALLOWED_HOSTS=\\(.*\\)/ALLOWED_HOSTS=\\1,'\"${NGROK_HOST}\"'/' .env 2>/dev/null || true
    fi
    if grep -q '^CORS_ALLOWED_ORIGINS=' .env 2>/dev/null; then
      sed -i 's|^CORS_ALLOWED_ORIGINS=\\(.*\\)|CORS_ALLOWED_ORIGINS=\\1,'\"${NGROK_URL}\"'|' .env 2>/dev/null || true
    fi
    # Recreate container so it picks up new ALLOWED_HOSTS from .env (restart keeps old env)
    (cd /home/${REMOTE_USER}/affordable-gadgets-backend && sudo docker compose up -d --force-recreate web 2>/dev/null) || (cd /home/${REMOTE_USER}/affordable-gadgets-backend && sudo docker-compose up -d --force-recreate web 2>/dev/null) || true
  fi
" 2>/dev/null || true

echo ""
echo "==> ngrok is running on the VM. Use this HTTPS URL in Vercel:"
echo ""
echo "  ${NGROK_URL}"
echo ""
echo "Vercel env vars:"
echo "  Admin:     REACT_APP_API_BASE_URL=${NGROK_URL}/api/inventory"
echo "  Frontend:  NEXT_PUBLIC_API_URL=${NGROK_URL}   (or add /api/inventory if your app expects it in the base URL)"
echo ""
echo "ALLOWED_HOSTS and CORS on the VM were updated to include the ngrok host. Redeploy the frontends on Vercel after setting the env vars above."
echo ""
