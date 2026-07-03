#!/usr/bin/env bash
set -euo pipefail

# reload-blogs-production.sh — Reload blog articles on AWS production API via SSM.
#
# Usage:
#   export AWS_API_INSTANCE_ID=i-...
#   export AWS_REGION=eu-north-1
#   ./scripts/reload-blogs-production.sh
#
# Or with terraform output:
#   AWS_API_INSTANCE_ID=$(terraform -chdir=deploy/terraform output -raw api_instance_id) \
#     ./scripts/reload-blogs-production.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

AWS_REGION="${AWS_REGION:-eu-north-1}"
if [[ -z "${AWS_API_INSTANCE_ID:-}" ]] && [[ -d deploy/terraform ]]; then
  AWS_API_INSTANCE_ID="$(terraform -chdir=deploy/terraform output -raw api_instance_id 2>/dev/null || true)"
fi
AWS_API_INSTANCE_ID="${AWS_API_INSTANCE_ID:?Set AWS_API_INSTANCE_ID or run terraform apply first}"

echo "Dry run load_blog_batch on ${AWS_API_INSTANCE_ID}..."
CMD_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$AWS_API_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "reload-blogs dry-run" \
  --parameters 'commands=["docker exec ag-api-web python manage.py load_blog_batch --dry-run"]' \
  --query 'Command.CommandId' --output text)

for i in $(seq 1 30); do
  STATUS=$(aws ssm get-command-invocation \
    --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$AWS_API_INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo Pending)
  [[ "$STATUS" == "Success" || "$STATUS" == "Failed" ]] && break
  sleep 3
done
aws ssm get-command-invocation \
  --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$AWS_API_INSTANCE_ID" \
  --query 'StandardOutputContent' --output text

echo ""
echo "Loading all blog batches (--force)..."
CMD_ID=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$AWS_API_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "reload-blogs force" \
  --parameters 'commands=["docker exec ag-api-web python manage.py load_blog_batch --force"]' \
  --query 'Command.CommandId' --output text)

for i in $(seq 1 60); do
  STATUS=$(aws ssm get-command-invocation \
    --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$AWS_API_INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo Pending)
  if [[ "$STATUS" == "Success" ]]; then
    aws ssm get-command-invocation \
      --region "$AWS_REGION" --command-id "$CMD_ID" --instance-id "$AWS_API_INSTANCE_ID" \
      --query 'StandardOutputContent' --output text
    echo "Done."
    exit 0
  fi
  [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" ]] && exit 1
  sleep 5
done
echo "Timed out waiting for load_blog_batch" >&2
exit 1
