#!/usr/bin/env bash
# Cloudflare Tunnel hostname checklist for AWS Phase 1 cutover.
# Run after monitoring deploy; update routes in Cloudflare Zero Trust dashboard.
set -euo pipefail

TF_DIR="$(cd "$(dirname "$0")/../terraform" && pwd)"
API_IP="$(terraform -chdir="$TF_DIR" output -raw api_private_ip 2>/dev/null || echo '<API_PRIVATE_IP>')"

cat <<EOF
Cloudflare Tunnel — configure these public hostnames:

  api.affordable-gadgetske.com
    → http://${API_IP}:8000

  grafana.affordable-gadgetske.com
    → http://localhost:3000

After updating routes:
  1. Verify: curl -sf https://api.affordable-gadgetske.com/health/
  2. Verify: curl -sf https://grafana.affordable-gadgetske.com/login
  3. Update Vercel: NEXT_PUBLIC_API_BASE_URL=https://api.affordable-gadgetske.com
  4. Redeploy shop + admin frontends on Vercel
  5. Run: ./deploy/scripts/verify-aws-phase1.sh
EOF
