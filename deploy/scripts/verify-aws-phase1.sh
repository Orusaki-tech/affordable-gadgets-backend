#!/usr/bin/env bash
# Post-deploy verification for AWS Phase 1.
set -euo pipefail

API_URL="${API_URL:-https://api.affordable-gadgetske.com}"
GRAFANA_URL="${GRAFANA_URL:-https://grafana.affordable-gadgetske.com}"

check() {
  local name="$1"
  local url="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url" || echo "000")
  if [[ "$code" =~ ^(200|302)$ ]]; then
    echo "OK  $name ($code) $url"
  else
    echo "FAIL $name ($code) $url" >&2
    return 1
  fi
}

FAIL=0
check "API health" "$API_URL/health/" || FAIL=1
check "API metrics" "$API_URL/metrics/" || FAIL=1
check "Datasource health" "$API_URL/api/inventory/analytics/datasource-health/" || FAIL=1
check "Grafana login" "$GRAFANA_URL/login" || FAIL=1

if [[ "$FAIL" -eq 0 ]]; then
  echo "✓ All checks passed"
else
  exit 1
fi
