#!/usr/bin/env bash
# Build and deploy Django API on the API EC2 instance via SSM (no local Docker).
set -euo pipefail

export PATH="/Users/shwariphones/Library/Python/3.14/bin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/deploy/terraform"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

cd "$TF_DIR"
BUCKET="$(terraform output -raw deploy_config_bucket)"
API_ID="$(terraform output -raw api_instance_id)"
REGION="$(terraform output -raw aws_region)"
API_PRIVATE_IP="$(terraform output -raw api_private_ip)"
MONITORING_PRIVATE_IP="$(terraform output -raw monitoring_private_ip)"
RDS_ENDPOINT="$(terraform output -raw rds_endpoint)"
RDS_USER="$(terraform output -raw rds_username)"
RDS_DB="$(terraform output -raw rds_db_name)"
DB_PASSWORD="$(aws ssm get-parameter --region "$REGION" --name "$(terraform output -raw db_password_ssm_parameter)" --with-decryption --query Parameter.Value --output text)"
export DB_PASSWORD RDS_ENDPOINT RDS_USER RDS_DB API_PRIVATE_IP MONITORING_PRIVATE_IP

if [[ ! -r "$ENV_FILE" ]]; then
  echo "Missing readable .env at $ENV_FILE" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

python3 <<PY
import os
from pathlib import Path

def load_env(path):
    data = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k] = v.strip().strip('"').strip("'")
    return data

env = load_env("$ENV_FILE")
secret = env.get("SECRET_KEY", "")
if not secret:
    raise SystemExit("SECRET_KEY missing in .env")

db_url = (
    f"postgresql://{os.environ['RDS_USER']}:{os.environ['DB_PASSWORD']}"
    f"@{os.environ['RDS_ENDPOINT']}:5432/{os.environ['RDS_DB']}?sslmode=require"
)

allowed = env.get(
    "ALLOWED_HOSTS",
    "api.affordable-gadgetske.com,localhost,127.0.0.1",
)
for ip in (os.environ.get("API_PRIVATE_IP", ""), os.environ.get("MONITORING_PRIVATE_IP", "")):
    if ip and ip not in allowed:
        allowed = f"{allowed},{ip}" if allowed else ip
cors = env.get(
    "CORS_ALLOWED_ORIGINS",
    "https://www.affordable-gadgetske.com,https://affordable-gadgets-frontend.vercel.app,https://admin.affordable-gadgetske.com",
)
frontend = env.get("FRONTEND_BASE_URL", "https://www.affordable-gadgetske.com")
csrf = env.get("CSRF_TRUSTED_ORIGINS", "https://api.affordable-gadgetske.com,https://www.affordable-gadgetske.com")

lines = [
    "DJANGO_ENV=production",
    "DEBUG=False",
    "DJANGO_SETTINGS_MODULE=store.settings_production",
    "PORT=8000",
    "RUN_MIGRATIONS_ON_STARTUP=1",
    f"SECRET_KEY={secret}",
    f"ALLOWED_HOSTS={allowed}",
    "SECURE_SSL_REDIRECT=false",
    f"DATABASE_URL={db_url}",
    f"CORS_ALLOWED_ORIGINS={cors}",
    f"FRONTEND_BASE_URL={frontend}",
    f"CSRF_TRUSTED_ORIGINS={csrf}",
    f"CLOUDINARY_CLOUD_NAME={env.get('CLOUDINARY_CLOUD_NAME','')}",
    f"CLOUDINARY_API_KEY={env.get('CLOUDINARY_API_KEY','')}",
    f"CLOUDINARY_API_SECRET={env.get('CLOUDINARY_API_SECRET','')}",
    f"PESAPAL_CONSUMER_KEY={env.get('PESAPAL_CONSUMER_KEY','')}",
    f"PESAPAL_CONSUMER_SECRET={env.get('PESAPAL_CONSUMER_SECRET','')}",
    f"PESAPAL_ENVIRONMENT={env.get('PESAPAL_ENVIRONMENT','production')}",
    f"PESAPAL_CALLBACK_URL={env.get('PESAPAL_CALLBACK_URL','https://api.affordable-gadgetske.com/api/payments/pesapal/callback/')}",
    f"PESAPAL_IPN_URL={env.get('PESAPAL_IPN_URL','https://api.affordable-gadgetske.com/api/payments/pesapal/ipn/')}",
    "GUNICORN_WORKERS=2",
    f"SENTRY_DSN={env.get('SENTRY_DSN','')}",
    f"SUPABASE_URL={env.get('SUPABASE_URL','')}",
    f"SUPABASE_ANON_KEY={env.get('SUPABASE_ANON_KEY','')}",
    "OTEL_ENABLED=false",
]
Path("$STAGE/api.env").write_text("\n".join(lines) + "\n")
PY

cat >"$STAGE/docker-compose.api.yml" <<'YAML'
services:
  web:
    build: ./app
    image: ag-api:production-latest
    container_name: ag-api-web
    restart: unless-stopped
    env_file: ./api.env
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
YAML

echo "→ Packaging source..."
tar -czf "$STAGE/source.tar.gz" \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='deploy/terraform/.terraform' \
  -C "$REPO_ROOT" .

echo "→ Uploading to s3://$BUCKET/production/api/"
aws s3 cp "$STAGE/source.tar.gz" "s3://$BUCKET/production/api/source.tar.gz"
aws s3 cp "$STAGE/api.env" "s3://$BUCKET/production/api/api.env"
aws s3 cp "$STAGE/docker-compose.api.yml" "s3://$BUCKET/production/api/docker-compose.api.yml"

REMOTE=$(cat <<'EOS'
set -eu
if ! docker compose version >/dev/null 2>&1; then
  COMPOSE_VERSION=v2.32.4
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
COMPOSE_ROOT=/opt/affordable-gadgets
BUCKET=__BUCKET__
mkdir -p "$COMPOSE_ROOT/app"
aws s3 cp "s3://$BUCKET/production/api/source.tar.gz" /tmp/source.tar.gz
aws s3 cp "s3://$BUCKET/production/api/api.env" "$COMPOSE_ROOT/api.env"
aws s3 cp "s3://$BUCKET/production/api/docker-compose.api.yml" "$COMPOSE_ROOT/docker-compose.api.yml"
chmod 600 "$COMPOSE_ROOT/api.env"
rm -rf "$COMPOSE_ROOT/app"/*
tar -xzf /tmp/source.tar.gz -C "$COMPOSE_ROOT/app"
cd "$COMPOSE_ROOT"
docker compose -f docker-compose.api.yml build --no-cache
docker compose -f docker-compose.api.yml up -d
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health/ >/dev/null; then
    echo "HEALTH_OK"
    docker exec ag-api-web python manage.py cleanup_carts --purge-anonymous --stale-months 2 || true
    docker exec ag-api-web python manage.py load_blog_batch --force --create-missing || true
    exit 0
  fi
  sleep 10
done
echo "HEALTH_FAILED"
docker logs ag-api-web --tail 80
exit 1
EOS
)
REMOTE="${REMOTE//__BUCKET__/$BUCKET}"

PARAMS_FILE="$(mktemp)"
python3 -c 'import json,sys; json.dump({"commands": [sys.argv[1]]}, open(sys.argv[2], "w"))' "$REMOTE" "$PARAMS_FILE"

echo "→ Deploying on $API_ID via SSM (build may take 5-10 min)..."
CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$API_ID" \
  --document-name AWS-RunShellScript \
  --comment "deploy-app-on-ec2" \
  --parameters "file://$PARAMS_FILE" \
  --timeout-seconds 3600 \
  --query Command.CommandId --output text)
rm -f "$PARAMS_FILE"

echo "CommandId: $CMD_ID"
for i in $(seq 1 60); do
  STATUS=$(aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" --instance-id "$API_ID" --query Status --output text 2>/dev/null || echo Pending)
  echo "  status=$STATUS (${i}/60)"
  if [[ "$STATUS" == "Success" ]]; then
    aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" --instance-id "$API_ID" --query StandardOutputContent --output text | tail -20
    echo "✓ API deployed on EC2"
    exit 0
  fi
  if [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" || "$STATUS" == "TimedOut" ]]; then
    aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" --instance-id "$API_ID" --query '[StandardOutputContent,StandardErrorContent]' --output text
    exit 1
  fi
  sleep 15
done
echo "Timed out waiting for SSM" >&2
exit 1
