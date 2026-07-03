#!/usr/bin/env bash
# Add Grafana SMTP credentials to the Ansible vault.
#
# Usage:
#   1. Get your SMTP credentials:
#      Option A: Check the running API container
#        docker exec ag-api-web env | grep EMAIL_HOST
#
#      Option B: SSH into an API GCE instance
#        gcloud compute ssh <instance> -- cat /opt/affordable-gadgets/api.env | grep EMAIL_HOST
#
#   2. Run this script:
#      bash scripts/add-grafana-smtp-to-vault.sh
#
#   You'll be prompted for the vault password once, then for the SMTP values.
set -euo pipefail

VAULT_FILE="deploy/ansible/secrets/production.vault.yml"

if [ ! -f "$VAULT_FILE" ]; then
  echo "Vault file not found: $VAULT_FILE"
  echo "Run this from the project root."
  exit 1
fi

echo "=== Add Grafana SMTP credentials to Ansible vault ==="
echo
echo "Retrieve your credentials first:"
echo "  ssh <monitoring-vm> \"sudo cat /opt/affordable-gadgets/api.env | grep EMAIL_HOST\""
echo
read -rp "grafana_smtp_user (e.g., your@gmail.com): " SMTP_USER
read -rsp "grafana_smtp_password (hidden): " SMTP_PASS
echo
read -rp "grafana_smtp_from [noreply@affordable-gadgetske.com]: " SMTP_FROM
SMTP_FROM="${SMTP_FROM:-noreply@affordable-gadgetske.com}"

# Decrypt, append, re-encrypt
TMP=$(mktemp)
ansible-vault decrypt "$VAULT_FILE" --output "$TMP" 2>/dev/null
cat >> "$TMP" << EOF

# Grafana SMTP for email alerts
grafana_smtp_user: "$SMTP_USER"
grafana_smtp_password: "$SMTP_PASS"
grafana_smtp_from: "$SMTP_FROM"
EOF
ansible-vault encrypt "$TMP" --output "$VAULT_FILE" 2>/dev/null
rm -f "$TMP"

echo
echo "Done! Vault updated at $VAULT_FILE"
echo
echo "Deploy to apply:"
echo "  ansible-playbook deploy/ansible/playbooks/monitoring.yml"
