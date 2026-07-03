#!/usr/bin/env bash
# Staging migration orchestrator: APIs → Terraform → Ansible vars → vault → deploy hints.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="${ROOT}/terraform"
TFVARS="${TF_DIR}/environments/staging.tfvars"
TFVARS_EXAMPLE="${TF_DIR}/environments/staging.tfvars.example"
APPLY="${APPLY:-}"

usage() {
  cat <<'EOF'
Usage: ./deploy/scripts/migrate-to-platform.sh [--apply]

  Without --apply: prepare tfvars, enable APIs, print next steps.
  With --apply:    run terraform apply (interactive approve unless TF_AUTO=1).

Environment:
  APPLY=1              same as --apply
  TF_AUTO=1            terraform apply -auto-approve
  SKIP_APIS=1          skip gcloud services enable
EOF
}

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -h|--help) usage; exit 0 ;;
  esac
done

need() {
  command -v "$1" >/dev/null || { echo "Missing: $1" >&2; exit 1; }
}

need gcloud
need terraform

if [[ ! -f "${TFVARS}" ]]; then
  echo "Creating ${TFVARS} from example..."
  cp "${TFVARS_EXAMPLE}" "${TFVARS}"
  echo "Edit project_id in ${TFVARS} if needed (default: project-07850c05-c54d-486b-80a)."
fi

PROJECT="$(grep -E '^project_id' "${TFVARS}" | sed 's/.*= *"\(.*\)".*/\1/')"
PROJECT="${PROJECT:-project-07850c05-c54d-486b-80a}"

if [[ "${SKIP_APIS:-}" != "1" ]]; then
  bash "${ROOT}/scripts/setup-gcp-apis.sh" "${PROJECT}"
fi

cd "${TF_DIR}"
terraform init -input=false

if [[ "${APPLY}" == "1" ]]; then
  if [[ "${TF_AUTO:-}" == "1" ]]; then
    terraform apply -auto-approve -input=false -var-file=environments/staging.tfvars
  else
    terraform apply -input=false -var-file=environments/staging.tfvars
  fi
  bash "${ROOT}/ansible/scripts/generate_ansible_vars_from_terraform.sh"
  bash "${ROOT}/scripts/init-staging-vault.sh"
  bash "${ROOT}/scripts/print-github-secrets.sh"
  echo ""
  echo "=== Manual steps ==="
  echo "1. ansible-vault encrypt deploy/ansible/secrets/staging.vault.yml (if not encrypted)"
  echo "2. Fill vault secrets (tunnel token, django secret_key, cloudinary, pesapal)"
  echo "3. DB: deploy/scripts/migrate-db-to-cloud-sql.sh (if moving from legacy VM)"
  echo "4. Build images: push to Artifact Registry (or run GitHub deploy-staging after secrets set)"
  echo "5. ansible-playbook -i deploy/ansible/inventory/staging deploy/ansible/playbooks/api.yml -e env_name=staging -e image_tag=staging-latest --ask-vault-pass"
  echo "6. Cloudflare tunnel origin -> api_lb_ip (deploy/docs/CLOUDFLARE-TUNNEL-PLATFORM.md)"
  echo "7. DNS: deploy/docs/DNS-STAGING.md"
else
  terraform plan -input=false -var-file=environments/staging.tfvars
  echo ""
  echo "Review plan, then: APPLY=1 ./deploy/scripts/migrate-to-platform.sh --apply"
fi
