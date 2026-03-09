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

# 3. Build .env for VM (inject ALLOWED_HOSTS and VM-specific vars)
if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Create .env with SECRET_KEY, CORS, Cloudinary, etc."
  exit 1
fi
ENV_REMOTE=".env.deploy.${IP}.tmp"
# Copy .env but strip vars we override or that don't apply on GCP (e.g. Railway Redis)
{ grep -v -e '^ALLOWED_HOSTS=' -e '^DATABASE_URL=' -e '^DJANGO_SETTINGS_MODULE=' -e '^DJANGO_ENV=' -e '^REDIS_URL=' .env 2>/dev/null || true; } > "${ENV_REMOTE}"
echo "ALLOWED_HOSTS=${IP},localhost,127.0.0.1" >> "${ENV_REMOTE}"
echo "DATABASE_URL=postgresql://affordable:affordable@postgres:5432/affordable_gadgets" >> "${ENV_REMOTE}"
echo "DJANGO_SETTINGS_MODULE=store.settings_production" >> "${ENV_REMOTE}"
echo "DJANGO_ENV=production" >> "${ENV_REMOTE}"
# REDIS_URL is not set on GCP (no Railway Redis) → Django uses LocMemCache

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
} > "${DEPLOY_SUMMARY}"
echo "==> Summary written to ${DEPLOY_SUMMARY}"

echo ""
echo "==> Deploy complete. Backend: http://${IP}:8000"
echo "    (Firewall for 22, 80, 443 is already in Terraform; no GCP Console needed.)"
echo ""
echo "    If you use ngrok for HTTPS, run: ./deploy/ngrok-on-vm.sh"
echo "    (Deploy overwrites .env; ngrok-on-vm.sh re-adds the ngrok host to ALLOWED_HOSTS.)"
