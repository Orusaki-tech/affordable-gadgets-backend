#!/usr/bin/env bash
# Print GitHub Actions secrets to configure after terraform apply.
set -euo pipefail

TF_DIR="$(cd "$(dirname "$0")/../terraform" && pwd)"
cd "$TF_DIR"

echo "Set these GitHub repository secrets (Settings → Secrets → Actions):"
echo ""
echo "AWS_ROLE_ARN=$(terraform output -raw github_deploy_role_arn 2>/dev/null || echo '<run terraform apply first>')"
echo "AWS_DEPLOY_CONFIG_BUCKET=$(terraform output -raw deploy_config_bucket 2>/dev/null || echo '<run terraform apply first>')"
echo "AWS_API_INSTANCE_ID=$(terraform output -raw api_instance_id 2>/dev/null || echo '<run terraform apply first>')"
echo "AWS_MONITORING_INSTANCE_ID=$(terraform output -raw monitoring_instance_id 2>/dev/null || echo '<run terraform apply first>')"
echo "AWS_API_PRIVATE_IP=$(terraform output -raw api_private_ip 2>/dev/null || echo '<run terraform apply first>')"
echo "AWS_RDS_ENDPOINT=$(terraform output -raw rds_endpoint 2>/dev/null || echo '<run terraform apply first>')"
echo "AWS_ANSIBLE_VAULT_PASSWORD=<your ansible-vault password>"
