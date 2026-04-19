#!/usr/bin/env bash
# Deploy backend to GCP: Terraform (VM + firewall) + Docker on the VM.
# No Ansible, no GCP Console. Run from backend repo root: ./deploy/deploy-gcp.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_DIR="/home/${REMOTE_USER}/affordable-gadgets-backend"
SKIP_TERRAFORM="${SKIP_TERRAFORM:-}"

echo "==> Backend root: ${BACKEND_ROOT}"
cd "${BACKEND_ROOT}"

# 1. Terraform apply (VM + firewall; firewall already allows 22, 80, 443)
if [[ -z "${SKIP_TERRAFORM}" ]]; then
  echo "==> Terraform apply..."
  cd "${TERRAFORM_DIR}"
  terraform init -input=false
  terraform apply -auto-approve -input=false
  cd "${BACKEND_ROOT}"
else
  echo "==> Skipping Terraform (SKIP_TERRAFORM=1)"
fi

# 2. Get VM IP and zone
cd "${TERRAFORM_DIR}"
IP="$(terraform output -raw external_ip 2>/dev/null || true)"
ZONE="$(terraform output -raw zone)"
INSTANCE_NAME="$(terraform output -raw instance_name)"
cd "${BACKEND_ROOT}"

if [[ -z "${IP}" ]]; then
  echo "ERROR: VM has no external IP (external_ip is empty)."
  echo "  This often happens after the VM was stopped—ephemeral IPs are released."
  echo "  Fix: Recreate the instance so it gets a new external IP:"
  echo "    cd ${TERRAFORM_DIR}"
  echo "    terraform apply -replace='google_compute_instance.backend' -auto-approve -input=false"
  echo "  Then run this deploy script again."
  echo "  To avoid this in future, set create_static_ip = true in deploy/terraform/terraform.tfvars"
  exit 1
fi

echo "==> VM: ${INSTANCE_NAME}, IP: ${IP}, zone: ${ZONE}"

# Optional hostnames for Django ALLOWED_HOSTS (e.g. current ngrok tunnel).
# Never hardcode a stale ngrok domain here — it caused DisallowedHost + fake "CORS" errors
# after ngrok restarts with a new URL.
#
# Priority:
#   1. DEPLOY_EXTRA_ALLOWED_HOSTS — comma-separated (e.g. your reserved ngrok domain)
#   2. SSH to VM and read ngrok's local API (127.0.0.1:4040) if the tunnel is already running
#   3. none — run ./deploy/ngrok-on-vm.sh after starting/changing ngrok
EXTRA_ALLOWED=""
if [[ -n "${DEPLOY_EXTRA_ALLOWED_HOSTS:-}" ]]; then
  EXTRA_ALLOWED="${DEPLOY_EXTRA_ALLOWED_HOSTS}"
  echo "==> ALLOWED_HOSTS extras from DEPLOY_EXTRA_ALLOWED_HOSTS: ${EXTRA_ALLOWED}"
else
  PROJECT_ID_PROBE="$(cd "${TERRAFORM_DIR}" && terraform output -raw project_id 2>/dev/null || true)"
  GCLOUD_SSH_PROBE=(gcloud compute ssh "${REMOTE_USER}@${INSTANCE_NAME}" --zone="${ZONE}")
  [[ -n "${PROJECT_ID_PROBE}" ]] && GCLOUD_SSH_PROBE+=(--project="${PROJECT_ID_PROBE}")
  TUNNEL_URL=""
  TUNNEL_URL=$("${GCLOUD_SSH_PROBE[@]}" --command="curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c \"
import sys, json
try:
    d = json.load(sys.stdin)
    for t in d.get('tunnels', []):
        u = t.get('public_url') or ''
        if u.startswith('https://'):
            print(u)
            break
except Exception:
    pass
\"" 2>/dev/null | tail -1) || true
  if [[ -n "${TUNNEL_URL}" ]]; then
    EXTRA_ALLOWED="$(echo "${TUNNEL_URL}" | sed -E 's|https?://([^/]+).*|\1|')"
    echo "==> Detected ngrok host on VM for ALLOWED_HOSTS: ${EXTRA_ALLOWED}"
  else
    echo "==> No ngrok tunnel detected on VM (or SSH/curl failed). Using IP + localhost only."
    echo "    If you use ngrok, start it on the VM then run: ./deploy/ngrok-on-vm.sh"
  fi
fi

# 3. Build .env for VM (inject ALLOWED_HOSTS and VM-specific vars)
if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Create .env with SECRET_KEY, CORS, Cloudinary, etc."
  exit 1
fi
ENV_REMOTE=".env.deploy.${IP}.tmp"
# Copy .env but strip vars we override or that don't apply on GCP (e.g. Railway Redis)
{ grep -v -e '^ALLOWED_HOSTS=' -e '^DATABASE_URL=' -e '^DJANGO_SETTINGS_MODULE=' -e '^DJANGO_ENV=' -e '^REDIS_URL=' .env 2>/dev/null || true; } > "${ENV_REMOTE}"
ALLOWED_HOSTS_VALUE="${IP},localhost,127.0.0.1"
if [[ -n "${EXTRA_ALLOWED}" ]]; then
  ALLOWED_HOSTS_VALUE="${ALLOWED_HOSTS_VALUE},${EXTRA_ALLOWED}"
fi
echo "ALLOWED_HOSTS=${ALLOWED_HOSTS_VALUE}" >> "${ENV_REMOTE}"
echo "DATABASE_URL=postgresql://affordable:affordable@postgres:5432/affordable_gadgets" >> "${ENV_REMOTE}"
echo "DJANGO_SETTINGS_MODULE=store.settings_production" >> "${ENV_REMOTE}"
echo "DJANGO_ENV=production" >> "${ENV_REMOTE}"
# REDIS_URL is not set on GCP (no Railway Redis) → Django uses LocMemCache

# Ensure CORS includes the admin app origin (browser origin), otherwise Vercel -> API requests will be blocked by CORS.
ADMIN_ORIGIN_DEFAULT="https://affordable-gadgets-admin.vercel.app"
if grep -q '^CORS_ALLOWED_ORIGINS=' "${ENV_REMOTE}"; then
  if ! grep -q "^CORS_ALLOWED_ORIGINS=.*${ADMIN_ORIGIN_DEFAULT}" "${ENV_REMOTE}"; then
    # Append while preserving existing values.
    sed -i '' "s|^CORS_ALLOWED_ORIGINS=\\(.*\\)|CORS_ALLOWED_ORIGINS=\\1,${ADMIN_ORIGIN_DEFAULT}|" "${ENV_REMOTE}" 2>/dev/null || true
  fi
else
  echo "CORS_ALLOWED_ORIGINS=${ADMIN_ORIGIN_DEFAULT}" >> "${ENV_REMOTE}"
fi

# Django production requires FRONTEND_BASE_URL (shop URL for emails, redirects). Local .env often omits it or uses localhost.
DEPLOY_FB_DEFAULT="${DEPLOY_FRONTEND_BASE_URL:-https://www.affordable-gadgetske.com}"
if grep -q '^FRONTEND_BASE_URL=' "${ENV_REMOTE}" 2>/dev/null; then
  _fb_line="$(grep '^FRONTEND_BASE_URL=' "${ENV_REMOTE}" | head -1)"
  _fb_val="${_fb_line#FRONTEND_BASE_URL=}"
  _fb_val="$(echo "${_fb_val}" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if [[ -z "${_fb_val}" ]] || echo "${_fb_val}" | grep -qE '(localhost|127\.0\.0\.1)'; then
    sed -i '' '/^FRONTEND_BASE_URL=/d' "${ENV_REMOTE}" 2>/dev/null || true
    echo "FRONTEND_BASE_URL=${DEPLOY_FB_DEFAULT}" >> "${ENV_REMOTE}"
    echo "==> Set FRONTEND_BASE_URL=${DEPLOY_FB_DEFAULT} (was missing, localhost, or empty)."
  fi
else
  echo "FRONTEND_BASE_URL=${DEPLOY_FB_DEFAULT}" >> "${ENV_REMOTE}"
  echo "==> Set FRONTEND_BASE_URL=${DEPLOY_FB_DEFAULT} (override via .env or DEPLOY_FRONTEND_BASE_URL=... when running deploy)."
fi
unset _fb_line _fb_val

# 4. Tarball backend (exclude git, venv, cache, local env, and the tarball itself)
TARBALL="backend-deploy.tar.gz"
echo "==> Creating tarball..."
tar --exclude='.git' --exclude='venv' --exclude='.venv' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.env' --exclude='staticfiles' --exclude='db.sqlite3' \
  --exclude='.env.*' --exclude="${TARBALL}" -czf "${TARBALL}" -C "${BACKEND_ROOT}" .

# 5. Copy to VM
PROJECT_ID="$(cd "${TERRAFORM_DIR}" && terraform output -raw project_id 2>/dev/null)"
echo "==> Copying to VM..."
if [[ -n "${PROJECT_ID}" ]]; then
  gcloud compute scp "${TARBALL}" "${ENV_REMOTE}" "${REMOTE_USER}@${INSTANCE_NAME}:~/" --zone="${ZONE}" --project="${PROJECT_ID}"
else
  gcloud compute scp "${TARBALL}" "${ENV_REMOTE}" "${REMOTE_USER}@${INSTANCE_NAME}:~/" --zone="${ZONE}"
fi

# 6. On VM: install Docker (if needed), untar, set .env, docker compose up
TAR_NAME="$(basename "${TARBALL}")"
ENV_NAME="$(basename "${ENV_REMOTE}")"
echo "==> Installing Docker and starting app on VM..."
GCLOUD_SSH=(gcloud compute ssh "${REMOTE_USER}@${INSTANCE_NAME}" --zone="${ZONE}")
[[ -n "${PROJECT_ID}" ]] && GCLOUD_SSH+=(--project="${PROJECT_ID}")
"${GCLOUD_SSH[@]}" --command="
  set -e
  export DEBIAN_FRONTEND=noninteractive
  if ! command -v docker &>/dev/null; then
    echo 'Installing Docker...'
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io
    sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || true
    sudo usermod -aG docker ${REMOTE_USER} || true
  fi
  if ! sudo docker compose version &>/dev/null; then
    echo 'Installing docker-compose standalone...'
    sudo curl -sL \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
  fi
  mkdir -p ${REMOTE_DIR}
  cd ${REMOTE_DIR}
  tar -xzf ~/${TAR_NAME} -C .
  mv ~/${ENV_NAME} .env
  if sudo docker compose up -d --build 2>/dev/null; then
    :
  else
    sudo docker-compose up -d --build
  fi
  echo 'Running WeasyPrint smoke check in web container...'
  if sudo docker compose exec -T web python -c \"from weasyprint import HTML; print('weasy ok')\" 2>/dev/null; then
    :
  else
    sudo docker-compose exec -T web python -c \"from weasyprint import HTML; print('weasy ok')\"
  fi
  echo 'Done. App should be at http://${IP}:8000'
"

# Cleanup
rm -f "${TARBALL}" "${ENV_REMOTE}"

# Write deploy summary for reference
DEPLOY_SUMMARY="${SCRIPT_DIR}/last-deploy.txt"
{
  echo "Deploy: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "VM: ${INSTANCE_NAME}"
  echo "External IP: ${IP}"
  echo "Zone: ${ZONE}"
  echo "Project: ${PROJECT_ID}"
  echo "Backend URL: http://${IP}:8000"
  if [[ -n "${EXTRA_ALLOWED:-}" ]]; then
    echo "ALLOWED_HOSTS extras (e.g. ngrok): ${EXTRA_ALLOWED}"
  fi
} > "${DEPLOY_SUMMARY}"
echo "==> Summary written to ${DEPLOY_SUMMARY}"

echo ""
echo "==> Deploy complete. Backend: http://${IP}:8000"
echo "    (Firewall for 22, 80, 443 is already in Terraform; no GCP Console needed.)"
echo ""
if [[ -n "${EXTRA_ALLOWED:-}" ]]; then
  echo "    ALLOWED_HOSTS on the VM includes the detected/extra hostname(s) above."
else
  echo "    Using ngrok? Start the tunnel on the VM, then run: ./deploy/ngrok-on-vm.sh"
  echo "    (That updates ALLOWED_HOSTS + recreates the web container for the current URL.)"
fi
echo "    Vercel must use REACT_APP_API_BASE_URL / NEXT_PUBLIC_API_URL matching that HTTPS URL; redeploy after the URL changes."
