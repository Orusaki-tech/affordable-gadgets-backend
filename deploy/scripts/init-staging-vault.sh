#!/usr/bin/env bash
# Create staging vault from example; optionally inject Cloud SQL password from Terraform.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAULT="${ROOT}/ansible/secrets/staging.vault.yml"
EXAMPLE="${ROOT}/ansible/secrets/staging.vault.yml.example"
TF_DIR="${ROOT}/terraform"

if [[ -f "${VAULT}" ]]; then
  echo "Vault already exists: ${VAULT}"
  echo "Edit it, then: ansible-vault encrypt ${VAULT}"
  exit 0
fi

cp "${EXAMPLE}" "${VAULT}"

# Password is managed externally via deploy/env/api.*.env files.
# Set db_password in the vault manually, or use gcloud to set/retrieve it:
#   gcloud sql users set-password affordable --instance=<instance> --password=<pw>

echo ""
echo "Next:"
echo "  1. Edit ${VAULT} — set secret_key, cloudflare_tunnel_token, cloudinary_*, pesapal_*"
echo "  2. ansible-vault encrypt ${VAULT}"
echo "  3. ansible-playbook -i ansible/inventory/staging ansible/playbooks/api.yml -e env_name=staging --ask-vault-pass"
