#!/usr/bin/env bash
# On-host watchdog: restart Prometheus/Grafana if health checks fail.
# Installed on the monitoring EC2 via user-data and deploy-monitoring.sh.
set -euo pipefail

COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/affordable-gadgets}"
LOG_TAG="ag-monitoring-watchdog"
GRAFANA_ENV="$COMPOSE_ROOT/monitoring/grafana.env"

log() {
  logger -t "$LOG_TAG" "$*"
  echo "$*"
}

check_url() {
  curl -sf --max-time 10 "$1" >/dev/null 2>&1
}

load_env_var() {
  local key="$1"
  if [[ -f "$GRAFANA_ENV" ]]; then
    grep -E "^${key}=" "$GRAFANA_ENV" | tail -1 | cut -d= -f2- | tr -d '"'
  fi
}

cd "$COMPOSE_ROOT"

API_PRIVATE_IP="$(load_env_var API_PRIVATE_IP)"
API_TOKEN="$(load_env_var GF_JSON_API_TOKEN)"

needs_restart=0
if ! check_url "http://localhost:3000/login"; then
  log "Grafana health check failed"
  needs_restart=1
fi
if ! check_url "http://localhost:9090/-/healthy"; then
  log "Prometheus health check failed"
  needs_restart=1
fi
if ! docker ps --format '{{.Names}}' | grep -qx 'ag-grafana'; then
  log "ag-grafana container not running"
  needs_restart=1
fi
if ! docker ps --format '{{.Names}}' | grep -qx 'ag-prometheus'; then
  log "ag-prometheus container not running"
  needs_restart=1
fi

# Probe Django over VPC (same path Grafana Infinity datasource uses)
if [[ -n "$API_PRIVATE_IP" && -n "$API_TOKEN" ]]; then
  if ! curl -sf --max-time 15 \
      -H "Authorization: Token ${API_TOKEN}" \
      "http://${API_PRIVATE_IP}:8000/api/inventory/analytics/datasource-health/" \
      | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('summary',{}).get('status')=='ok'"; then
    log "Django datasource health check failed over VPC (${API_PRIVATE_IP})"
    needs_restart=1
  fi
else
  log "Skipping Django datasource probe (API_PRIVATE_IP or GF_JSON_API_TOKEN missing in grafana.env)"
fi

if [[ "$needs_restart" -eq 1 ]]; then
  log "Restarting monitoring stack"
  docker compose -f docker-compose.monitoring.yml --env-file monitoring/grafana.env up -d --remove-orphans
  sleep 15
  if check_url "http://localhost:3000/login" && check_url "http://localhost:9090/-/healthy"; then
    log "Monitoring stack recovered"
  else
    log "Monitoring stack still unhealthy after restart"
    exit 1
  fi
fi
