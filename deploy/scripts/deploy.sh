#!/usr/bin/env bash
# Provision AWS Phase 1 infrastructure and generate Ansible vars.
#
# Usage (from repo root):
#   ./deploy/scripts/deploy.sh plan
#   ./deploy/scripts/deploy.sh apply
#   APPLY=1 ./deploy/scripts/deploy.sh apply
#
# Requires: terraform, aws CLI (authenticated), jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deploy/terraform"
TFVARS="$TF_DIR/environments/production.tfvars"
ACTION="${1:-plan}"

cd "$TF_DIR"

echo "→ AWS account:"
aws sts get-caller-identity

terraform init -input=false

if [[ "$ACTION" == "plan" ]]; then
  terraform plan -var-file="$TFVARS" -out=phase1.tfplan
  echo "Run: APPLY=1 $0 apply"
  exit 0
fi

if [[ "$ACTION" == "apply" ]]; then
  if [[ -f phase1.tfplan ]]; then
    terraform apply phase1.tfplan
  else
    terraform apply -var-file="$TFVARS" -auto-approve
  fi

  terraform output -json > /tmp/ag-aws-terraform-output.json
  python3 "$SCRIPT_DIR/generate_ansible_vars.py" /tmp/ag-aws-terraform-output.json

  echo ""
  echo "✓ Infrastructure ready. Next steps:"
  echo "  1. Copy secrets: cp deploy/ansible/secrets/production.vault.yml.example deploy/ansible/secrets/production.vault.yml"
  echo "  2. Set db_password from SSM: aws ssm get-parameter --name \$(terraform output -raw db_password_ssm_parameter) --with-decryption"
  echo "  3. ansible-vault encrypt deploy/ansible/secrets/production.vault.yml"
  echo "  4. ./deploy/scripts/deploy.sh push-image"
  echo "  5. ansible-playbook deploy/ansible/playbooks/api.yml --ask-vault-pass"
  echo "  6. DEPLOY_TUNNEL_ON_MONITORING=1 ./deploy/scripts/deploy-monitoring.sh"
  exit 0
fi

if [[ "$ACTION" == "push-image" ]]; then
  REGION="$(terraform output -raw aws_region)"
  REPO="$(terraform output -raw ecr_repository_url)"
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPO%/*}"
  docker build -t "$REPO:production-latest" "$REPO_ROOT"
  docker push "$REPO:production-latest"
  echo "✓ Pushed $REPO:production-latest"
  exit 0
fi

if [[ "$ACTION" == "migrate" ]]; then
  INSTANCE_ID="$(terraform output -raw api_instance_id)"
  REGION="$(terraform output -raw aws_region)"
  CMD_ID=$(aws ssm send-command \
    --region "$REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --parameters 'commands=["docker exec ag-api-web python manage.py migrate --noinput"]' \
    --query 'Command.CommandId' --output text)
  echo "→ Migration command: $CMD_ID (check with aws ssm get-command-invocation)"
  exit 0
fi

if [[ "$ACTION" == "load-blogs" ]]; then
  INSTANCE_ID="$(terraform output -raw api_instance_id)"
  REGION="$(terraform output -raw aws_region)"
  CMD_ID=$(aws ssm send-command \
    --region "$REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --parameters 'commands=["docker exec ag-api-web python manage.py load_blog_batch --force --create-missing"]' \
    --query 'Command.CommandId' --output text)
  echo "→ load_blog_batch command: $CMD_ID"
  exit 0
fi

if [[ "$ACTION" == "seo-maintenance" ]]; then
  exec "$SCRIPT_DIR/run-seo-maintenance.sh" "${2:-audit}"
fi

echo "Unknown action: $ACTION (plan|apply|push-image|migrate|load-blogs|seo-maintenance)" >&2
exit 1
