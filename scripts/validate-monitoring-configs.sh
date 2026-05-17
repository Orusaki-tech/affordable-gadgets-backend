#!/usr/bin/env bash
# Validate all monitoring configuration files.
# Run locally or in CI:  bash scripts/validate-monitoring-configs.sh
set -euo pipefail

ERRORS=0
MONITORING_DIR="deploy/ansible/roles/monitoring_compose"
STANDALONE_DIR="deploy/monitoring"

echo "=== Validating monitoring configs ==="

# ── JSON validation for Grafana dashboards ──
echo "--- Checking Grafana dashboard JSON files ---"
for json_file in "$MONITORING_DIR"/files/*.json "$STANDALONE_DIR"/grafana/dashboards/*.json; do
  [ -f "$json_file" ] || continue
  if python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null; then
    echo "  OK: $json_file"
  else
    echo "  FAIL: $json_file is not valid JSON"
    ERRORS=$((ERRORS + 1))
  fi
done

# ── Unique dashboard UIDs ──
echo "--- Checking for unique dashboard UIDs ---"
ALL_UIDS=$(python3 -c "
import json, glob, sys
uids = set()
for f in glob.glob('$MONITORING_DIR/files/*.json') + glob.glob('$STANDALONE_DIR/grafana/dashboards/*.json'):
    try:
        d = json.load(open(f))
        uid = d.get('uid')
        if uid in uids:
            print(f'DUPLICATE UID: {uid} in {f}')
            sys.exit(1)
        uids.add(uid)
    except: pass
print('All UIDs unique')
" 2>&1)
echo "  $ALL_UIDS"

# ── YAML validation for Prometheus rules (skip Jinja2 templates) ──
echo "--- Checking Prometheus alert rule files ---"
for yaml_file in "$MONITORING_DIR"/files/*.yml; do
  [ -f "$yaml_file" ] || continue
  if python3 -c "import yaml; yaml.safe_load(open('$yaml_file'))" 2>/dev/null; then
    echo "  OK: $yaml_file"
  else
    echo "  FAIL: $yaml_file is not valid YAML"
    ERRORS=$((ERRORS + 1))
  fi
done

# ── Prometheus rule check (if promtool available) ──
if command -v promtool &> /dev/null; then
  echo "--- Checking Prometheus rules with promtool ---"
  for rule_file in "$MONITORING_DIR"/files/alerts.yml; do
    [ -f "$rule_file" ] || continue
    if promtool check rules "$rule_file" > /dev/null 2>&1; then
      echo "  OK: $rule_file"
    else
      echo "  FAIL: $rule_file failed promtool check"
      promtool check rules "$rule_file" 2>&1 | sed 's/^/    /'
      ERRORS=$((ERRORS + 1))
    fi
  done
else
  echo "  (promtool not available, skipping rule validation)"
fi

# ── Grafana dashboard schema checks ──
echo "--- Checking Grafana dashboard schema basics ---"
for json_file in "$MONITORING_DIR"/files/*.json; do
  [ -f "$json_file" ] || continue
  python3 -c "
import json

d = json.load(open('$json_file'))
errors = []
if not d.get('title'):
    errors.append('missing title')
if not d.get('uid'):
    errors.append('missing uid')
if not isinstance(d.get('panels'), list):
    errors.append('missing or invalid panels list')
else:
    for i, p in enumerate(d['panels']):
        if not p.get('type'):
            errors.append(f'panel[{i}] missing type')
        if not p.get('targets'):
            errors.append(f'panel[{i}] missing targets')
if errors:
    print(f'  WARN: {\"$json_file\"} — {\", \".join(errors)}')
else:
    print(f'  OK: $json_file ({\"$json_file\"})')
" 2>&1
done

echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "✓ All monitoring configs valid"
  exit 0
else
  echo "✗ $ERRORS validation error(s) found"
  exit 1
fi
