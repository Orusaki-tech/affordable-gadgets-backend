#!/usr/bin/env bash
# Print GitHub Actions secrets/vars to configure after terraform apply.
set -euo pipefail

TF_DIR="$(cd "$(dirname "$0")/../terraform" && pwd)"
cd "${TF_DIR}"

if ! terraform output -json >/dev/null 2>&1; then
  echo "Run terraform apply first." >&2
  exit 1
fi

PROJECT="$(terraform output -raw project_id 2>/dev/null || true)"
ZONE="$(terraform output -raw zone 2>/dev/null || true)"
WIF="$(terraform output -raw gcp_wif_provider 2>/dev/null || true)"
DEPLOY_SA="$(terraform output -raw gcp_deploy_sa_email 2>/dev/null || true)"
API_MIG="$(terraform output -raw api_mig_name 2>/dev/null || true)"
SHOP_MIG="$(terraform output -raw shop_mig_name 2>/dev/null || true)"
ADMIN_MIG="$(terraform output -raw admin_mig_name 2>/dev/null || true)"
CONN="$(terraform output -raw cloud_sql_connection_name 2>/dev/null || true)"
API_LB="$(terraform output -raw api_lb_ip 2>/dev/null || true)"
SHOP_LB="$(terraform output -raw shop_lb_ip 2>/dev/null || true)"
ADMIN_LB="$(terraform output -raw admin_lb_ip 2>/dev/null || true)"
TUNNEL="$(terraform output -raw tunnel_instance_name 2>/dev/null || true)"

cat <<EOF

=== GitHub repository secrets (affordable-gadgets-backend) ===
GCP_PROJECT_ID              = ${PROJECT}
GCP_ZONE                    = ${ZONE}
STAGING_API_MIG_NAME        = ${API_MIG}
STAGING_SHOP_MIG_NAME       = ${SHOP_MIG}
STAGING_ADMIN_MIG_NAME      = ${ADMIN_MIG}
CLOUD_SQL_CONNECTION_NAME   = ${CONN}

GCP_WIF_PROVIDER            = ${WIF:-<run terraform apply with github_repository set>}
GCP_DEPLOY_SA               = ${DEPLOY_SA:-<from terraform output gcp_deploy_sa_email>}

# Optional: for migrate job in deploy-staging.yml
STAGING_DATABASE_URL        = postgresql://affordable:PASSWORD@CLOUD_SQL_PRIVATE_IP:5432/affordable_gadgets
  (password: managed via deploy/env/api.*.env; set with: gcloud sql users set-password ...)

=== GitHub repository variables ===
STAGING_API_URL             = https://api-staging.affordable-gadgetske.com
ENABLE_CLOUD_SQL_MIGRATE    = true   (after DB migrated)

=== DNS / Cloudflare (staging) ===
shop A record               -> ${SHOP_LB}
admin-staging A record      -> ${ADMIN_LB}
api-staging tunnel origin   -> http://${API_LB}  (LB port 80, not :8000)

=== Tunnel VM (Ansible inventory) ===
gcloud compute ssh ${TUNNEL} --zone=${ZONE} --project=${PROJECT} --tunnel-through-iap

EOF
