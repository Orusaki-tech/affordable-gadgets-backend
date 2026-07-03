#!/usr/bin/env bash
# Run SEO maintenance on the production API host (structural fixes + slug redirects).
#
# Usage:
#   ./deploy/scripts/run-seo-maintenance.sh audit
#   ./deploy/scripts/run-seo-maintenance.sh apply

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deploy/terraform"
ACTION="${1:-audit}"

cd "$TF_DIR"
INSTANCE_ID="$(terraform output -raw api_instance_id)"
REGION="$(terraform output -raw aws_region)"

DRY_RUN_FLAG=""
if [[ "$ACTION" == "audit" ]]; then
  DRY_RUN_FLAG="--dry-run"
fi

REMOTE_CMD=$(cat <<EOF
docker exec ag-api-web python manage.py migrate --noinput
docker exec ag-api-web python manage.py seo_structural_maintenance $DRY_RUN_FLAG
EOF
)

PARAMS=$(REMOTE_CMD | python3 -c 'import json,sys; print(json.dumps({"commands": [sys.stdin.read()]}))')

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "$PARAMS" \
  --query 'Command.CommandId' --output text)

echo "→ SEO maintenance ($ACTION) command: $CMD_ID"
echo "→ Waiting for result..."

for _ in $(seq 1 45); do
  STATUS=$(aws ssm get-command-invocation \
    --region "$REGION" \
    --command-id "$CMD_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo "Pending")
  if [[ "$STATUS" == "Success" || "$STATUS" == "Failed" || "$STATUS" == "Cancelled" || "$STATUS" == "TimedOut" ]]; then
    break
  fi
  sleep 2
done

aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --output json | python3 -c '
import json, sys
data = json.load(sys.stdin)
print("Status:", data.get("Status"))
stdout = (data.get("StandardOutputContent") or "").strip()
stderr = (data.get("StandardErrorContent") or "").strip()
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
sys.exit(0 if data.get("Status") == "Success" else 1)
'
