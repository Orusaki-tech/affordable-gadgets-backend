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

if command -v terraform >/dev/null 2>&1 && [[ -d "${TF_DIR}" ]]; then
  if pw="$(cd "${TF_DIR}" && terraform output -raw cloud_sql_db_password 2>/dev/null)"; then
    if [[ -n "${pw}" && "${pw}" != "null" ]]; then
      # macOS/BSD sed
      if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "s/db_password: \"CHANGE_ME\"/db_password: \"${pw}\"/" "${VAULT}"
      else
        sed -i '' "s/db_password: \"CHANGE_ME\"/db_password: \"${pw}\"/" "${VAULT}"
      fi
      echo "Injected cloud_sql_db_password from terraform output."
    fi
  fi
fi

echo ""
echo "Next:"
echo "  1. Edit ${VAULT} — set secret_key, cloudflare_tunnel_token, cloudinary_*, pesapal_*"
echo "  2. ansible-vault encrypt ${VAULT}"
echo "  3. ansible-playbook -i ansible/inventory/staging ansible/playbooks/api.yml -e env_name=staging --ask-vault-pass"
