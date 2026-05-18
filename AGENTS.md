# Session: 2026-05-18 — Dashboard No Data / Errors + Tunnel Down

## Problems Fixed

### 1. Cloudflare Tunnel (Error 1033)
- cloudflared entered bad state after previous VM reboot
- Docker restart policy (`unless-stopped`) failed to recover it
- **Fix**: `gcloud compute instances reset` — hard power-cycle. Startup script metadata was used to re-run cloudflared on boot, then cleaned up.
- **To avoid**: CI/CD does NOT touch the monitoring VM, so this won't recur on normal deploys.

### 2. Dashboard period panels: "No data" and "errors"
- Template variable `$period` had `type: custom` — Grafana does NOT expand custom-type variables inside PromQL `[..]` brackets (bug persists even in v13.0.1 for `custom` type).
- **Fix**: Changed `type` from `custom` → `interval` in the dashboard JSON.
  - `query` changed from `"1h : Hourly, 24h : Daily, ..."` → `"1h,24h,7d,30d"`
  - `options` texts changed from `"Hourly"` → `"1h"`, etc.
- Only `interval` type variables expand correctly in `[$var]` PromQL syntax.

### 3. Dashboard time-series panels missing `or vector(0)`
- 6 queries across 4 panels had no `or vector(0)` fallback:
  - Revenue Trend: `sum(increase(revenue_earned_total[$period])) by (brand)`
  - Orders by Status: `sum(increase(orders_total[$period])) by (status)`
  - Leads vs Conversions (2 queries): `sum(increase(leads_created_total[$period])) by (brand)` and same for `leads_converted_total`
  - Customers & Revenue (2 queries): `sum(increase(customers_registered_total[$period]))` and `sum(increase(revenue_earned_total[$period]))`
- **Fix**: Appended `or vector(0)` to all 6.

## Key State

### Counters registered (HELP/TYPE lines exist) but NEVER incrementeds
- All 5 counters: `revenue_earned_total`, `leads_created_total`, `leads_converted_total`, `customers_registered_total`, `new_orders_total`
- They exist in all 3 API instances' registries but have zero data points
- **Root cause**: Gunicorn multi-process. Each worker process has its own `prometheus_client` registry. Counters incremented in one worker (e.g., payment complete) are invisible to the `/metrics/` handler running in a different worker. The `/metrics/` response only shows its own process's counters.
- Only `http_requests_total` works because the same worker that serves `/metrics/` also counts its own requests via middleware.
- **Solution options**: (a) Set `PROMETHEUS_MULTIPROC_DIR` for shared file-based registry, (b) Read counter values from DB in `refresh_business_metrics()` like the gauges do, (c) Wait for real traffic.

### Dashboard queries verified working (return `value=0`):
```promql
sum(increase(revenue_earned_total[24h])) or vector(0)        # → 0
sum(increase(customers_registered_total[24h])) or vector(0)   # → 0
sum(increase(leads_created_total[24h])) by (brand) or vector(0) # → 0
sum(increase(orders_total[24h])) by (status) or vector(0)     # → 0
```

### Dashboard file locations (BOTH must stay in sync):
- `deploy/ansible/roles/monitoring_compose/files/executive-kpi-dashboard.json` — Ansible source of truth
- `deploy/monitoring/grafana/dashboards/executive-kpi-dashboard.json` — local copy
- Deployed to VM at: `/opt/affordable-gadgets/monitoring/grafana/dashboards/executive-kpi-dashboard.json`

## Files Modified
- `deploy/ansible/roles/monitoring_compose/files/executive-kpi-dashboard.json` — added `or vector(0)` to 6 queries, changed `$period` type to `interval`
- `deploy/monitoring/grafana/dashboards/executive-kpi-dashboard.json` — same changes (copy)

## Open Items
- SMTP alerts blocked: `grafana_smtp_user` / `grafana_smtp_password` empty in vault (need Gmail app password)
- Dashboard will show 0 for all period panels until counters are incremented by real user events (or multi-process issue is fixed)
