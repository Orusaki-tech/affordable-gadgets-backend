#!/bin/sh
set -e

PROMETHEUS_STORAGE="/prometheus"
GRAFANA_DATA="/var/lib/grafana"

if [ -d /data ]; then
  PROMETHEUS_STORAGE="/data/prometheus"
  GRAFANA_DATA="/data/grafana"
  mkdir -p "$PROMETHEUS_STORAGE" "$GRAFANA_DATA"
  chown -R grafana:472 /data 2>/dev/null || true
fi

mkdir -p "$PROMETHEUS_STORAGE" "$GRAFANA_DATA"

if [ -n "${FLY_APP_NAME:-}" ]; then
  export GF_SERVER_ROOT_URL="https://${FLY_APP_NAME}.fly.dev"
fi

prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path="$PROMETHEUS_STORAGE" \
  --storage.tsdb.retention.time=15d \
  --web.listen-address=127.0.0.1:9090 \
  &

export GF_PATHS_DATA="$GRAFANA_DATA"
exec /run.sh
