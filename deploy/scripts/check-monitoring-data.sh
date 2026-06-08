#!/usr/bin/env bash
# Inspect Prometheus/Grafana Docker volumes on the monitoring VM.
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-project-07850c05-c54d-486b-80a}"
ZONE="${GCP_ZONE:-us-east1-b}"
INSTANCE="${MONITORING_INSTANCE:-affordable-gadgets-production-monitoring}"

echo "Checking monitoring data on ${INSTANCE}..."

gcloud compute ssh "${INSTANCE}" \
  --project="${PROJECT}" \
  --zone="${ZONE}" \
  --tunnel-through-iap \
  --command='
    echo "=== Docker containers ==="
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    echo ""
    echo "=== Docker volumes ==="
    docker volume ls 2>/dev/null || true
    echo ""
    echo "=== Prometheus / Grafana volume sizes ==="
    for v in $(docker volume ls -q 2>/dev/null | grep -E "prometheus|grafana" || true); do
      docker run --rm -v "${v}:/data" busybox du -sh /data 2>/dev/null || true
    done
    echo ""
    echo "=== Recent compose dir ==="
    ls -la /opt/affordable-gadgets/monitoring 2>/dev/null | head -5 || echo "(compose dir not found)"
  '

echo ""
echo "GCP disk snapshots (monitoring VM boot disk):"
DISK=$(gcloud compute instances describe "${INSTANCE}" \
  --project="${PROJECT}" --zone="${ZONE}" \
  --format='value(disks[0].source.basename())' 2>/dev/null || true)
if [[ -n "${DISK}" ]]; then
  gcloud compute snapshots list --project="${PROJECT}" \
    --filter="sourceDisk:${DISK}" \
    --format="table(name,creationTimestamp,diskSizeGb)" \
    --limit=10 2>/dev/null || echo "(no snapshots or permission denied)"
else
  echo "Could not resolve boot disk for ${INSTANCE}"
fi
