#!/usr/bin/env bash
# Cloudflare Tunnel hostname checklist for AWS Phase 1 cutover.
# Tunnel (cloudflared) runs on the API EC2 — not the monitoring VM.
set -euo pipefail

TF_DIR="$(cd "$(dirname "$0")/../terraform" && pwd)"
MONITORING_IP="$(terraform -chdir="$TF_DIR" output -raw monitoring_private_ip 2>/dev/null || echo '<MONITORING_PRIVATE_IP>')"

cat <<EOF
Cloudflare Tunnel — public hostnames (connector on API EC2):

  api.affordable-gadgetske.com
    → http://localhost:8000

  grafana.affordable-gadgetske.com
    → http://localhost:3000
    (ag-grafana-proxy on API forwards to monitoring at ${MONITORING_IP}:3000)

After updating routes:
  1. Verify: curl -sf https://api.affordable-gadgetske.com/health/
  2. Verify: curl -sf https://grafana.affordable-gadgetske.com/login
  3. Update Vercel: NEXT_PUBLIC_API_BASE_URL=https://api.affordable-gadgetske.com
  4. Redeploy shop + admin frontends on Vercel
  5. Run: ./deploy/scripts/verify-aws-phase1.sh
EOF
