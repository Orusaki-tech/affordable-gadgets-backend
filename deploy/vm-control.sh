#!/usr/bin/env bash
# Stop or start the GCP backend VM. Run from backend repo root: ./deploy/vm-control.sh stop|start|status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"

ACTION="${1:-}"
if [[ -z "${ACTION}" ]] || [[ "${ACTION}" != "stop" && "${ACTION}" != "start" && "${ACTION}" != "status" ]]; then
  echo "Usage: $0 stop|start|status"
  echo "  stop   - Stop the GCP VM (saves cost; Django and ngrok will be down)"
  echo "  start  - Start the GCP VM (takes ~1 min; then run ngrok-on-vm.sh if needed)"
  echo "  status - Show VM run status"
  exit 1
fi

cd "${TERRAFORM_DIR}"
INSTANCE_NAME="$(terraform output -raw instance_name 2>/dev/null)" || { echo "Run Terraform first (deploy-gcp.sh or terraform apply)."; exit 1; }
ZONE="$(terraform output -raw zone)"
PROJECT_ID="$(terraform output -raw project_id 2>/dev/null)" || true

if [[ -n "${PROJECT_ID}" ]]; then
  PROJECT_ARG="--project=${PROJECT_ID}"
else
  PROJECT_ARG=""
fi

case "${ACTION}" in
  stop)
    echo "==> Stopping VM ${INSTANCE_NAME} (zone: ${ZONE})..."
    gcloud compute instances stop "${INSTANCE_NAME}" --zone="${ZONE}" ${PROJECT_ARG}
    echo "==> VM stopped. Start with: $0 start"
    ;;
  start)
    echo "==> Starting VM ${INSTANCE_NAME} (zone: ${ZONE})..."
    gcloud compute instances start "${INSTANCE_NAME}" --zone="${ZONE}" ${PROJECT_ARG}
    echo "==> VM started. Wait ~1 min, then run ./deploy/ngrok-on-vm.sh if you need the tunnel."
    ;;
  status)
    gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" ${PROJECT_ARG} --format="table(name,zone.basename(),status)"
    ;;
esac
