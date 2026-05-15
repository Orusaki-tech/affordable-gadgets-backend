#!/usr/bin/env bash
# Wrapper for k6 load tests. Requires: https://grafana.com/docs/k6/latest/set-up/install-k6/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE_URL="${BASE_URL:-https://api-staging.affordable-gadgetske.com}"
BRAND_CODE="${BRAND_CODE:-AFFORDABLE_GADGETS}"

usage() {
  cat <<'EOF'
Usage: ./deploy/loadtest/run.sh <smoke|ramp|2m-hour|browse> [extra k6 args...]

  smoke     ~2 min at 20 req/s (default)
  ramp      ramp to TARGET_RPS (default 556), hold, ramp down
  2m-hour   sustained TARGET_RPS for DURATION (default 556 req/s for 1h ≈ 2M requests)
  browse    legacy stage-based script

Environment:
  BASE_URL       API origin (default: api-staging)
  BRAND_CODE     X-Brand-Code header
  TARGET_RPS     Requests per second (default: 556 for 2m-hour)
  DURATION       k6 duration string (default: 1h for 2m-hour, 2m for smoke)

Examples:
  ./deploy/loadtest/run.sh smoke
  TARGET_RPS=300 DURATION=20m ./deploy/loadtest/run.sh 2m-hour
  BASE_URL=https://api.affordable-gadgetske.com ./deploy/loadtest/run.sh ramp
EOF
}

if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 not found. Install: https://grafana.com/docs/k6/latest/set-up/install-k6/" >&2
  exit 1
fi

SCENARIO="${1:-}"
shift || true

case "$SCENARIO" in
  smoke)   SCRIPT="$ROOT/k6-smoke.js" ;;
  ramp)    SCRIPT="$ROOT/k6-ramp.js" ;;
  2m-hour) SCRIPT="$ROOT/k6-2m-hour.js" ;;
  browse)  SCRIPT="$ROOT/k6-browse.js" ;;
  -h|--help|help|"")
    usage
    exit 0
    ;;
  *)
    echo "Unknown scenario: $SCENARIO" >&2
    usage
    exit 1
    ;;
esac

exec k6 run \
  -e "BASE_URL=$BASE_URL" \
  -e "BRAND_CODE=$BRAND_CODE" \
  "$SCRIPT" \
  "$@"
