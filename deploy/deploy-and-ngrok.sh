#!/usr/bin/env bash
# Run the full laptop workflow: deploy backend to GCP, then start/update ngrok on the VM.
# You do NOT need to SSH into the VM — both scripts use gcloud from your machine.
# ngrok-on-vm.sh updates ALLOWED_HOSTS, CORS, PESAPAL_IPN_URL for the current tunnel, and recreates web.
#
# From backend repo root:
#   ./deploy/deploy-and-ngrok.sh
#
# Optional:
#   SKIP_TERRAFORM=1 ./deploy/deploy-and-ngrok.sh     # deploy code only (skip terraform apply)
#   SKIP_NGROK=1 ./deploy/deploy-and-ngrok.sh         # deploy only, no ngrok step
#   NGROK_AUTH_TOKEN=... ./deploy/deploy-and-ngrok.sh
#
# Reduce SSH passphrase prompts (once per terminal session):
#   eval "$(ssh-agent -s)" && ssh-add ~/.ssh/google_compute_engine

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

"${ROOT}/deploy/deploy-gcp.sh"

if [[ "${SKIP_NGROK:-}" == "1" ]]; then
  echo "==> SKIP_NGROK=1 — skipping ./deploy/ngrok-on-vm.sh"
  exit 0
fi

exec "${ROOT}/deploy/ngrok-on-vm.sh"
