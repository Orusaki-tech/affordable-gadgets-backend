#!/usr/bin/env bash
# Deploy cloudflared to tunnel VM via gcloud (bypasses Ansible IAP DNS issues).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT=project-07850c05-c54d-486b-80a
ZONE=us-central1-a
INSTANCE=affordable-gadgets-staging-tunnel
TOKEN="$(cd "${ROOT}/ansible" && ansible-vault view secrets/staging.vault.yml --vault-password-file .vault_pass 2>/dev/null | python3 -c "import sys,yaml; print(yaml.safe_load(sys.stdin).get('cloudflare_tunnel_token',''))")"

if [[ -z "${TOKEN}" ]]; then
  echo "cloudflare_tunnel_token missing in vault" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

cat > "${TMP}/docker-compose.tunnel.yml" <<'YML'
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: ag-cloudflared
    restart: unless-stopped
    env_file:
      - tunnel.env
    command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
    environment:
      CLOUDFLARE_TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
YML

echo "CLOUDFLARE_TUNNEL_TOKEN=${TOKEN}" > "${TMP}/tunnel.env"

gcloud compute scp "${TMP}/docker-compose.tunnel.yml" "${TMP}/tunnel.env" \
  "${INSTANCE}:/tmp/" --zone="${ZONE}" --project="${PROJECT}" --tunnel-through-iap

gcloud compute ssh "${INSTANCE}" --zone="${ZONE}" --project="${PROJECT}" --tunnel-through-iap --command="
set -e
sudo apt-get update -qq
sudo apt-get install -y -qq docker.io
sudo systemctl enable docker && sudo systemctl start docker
sudo mkdir -p /opt/affordable-gadgets
sudo mv /tmp/docker-compose.tunnel.yml /tmp/tunnel.env /opt/affordable-gadgets/
cd /opt/affordable-gadgets && sudo docker compose -f docker-compose.tunnel.yml --env-file tunnel.env up -d 2>/dev/null || \
  (sudo curl -fsSL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose && \
   sudo chmod +x /usr/local/bin/docker-compose && sudo docker-compose -f docker-compose.tunnel.yml --env-file tunnel.env up -d)
sudo docker ps
echo TUNNEL_DEPLOYED
"

API_LB="$(cd "${ROOT}/terraform" && terraform output -raw api_lb_ip)"
echo ""
echo "Set Cloudflare tunnel public hostname origin to: http://${API_LB}  (port 80, not :8000)"
