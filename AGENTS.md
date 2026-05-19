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

# Session: 2026-05-19 — Grafana JSON API 502 Error

## Problem Fixed

### JSON API datasource returning 502 Bad Gateway
- **Error**: Grafana JSON API datasource (`marcusolsson-json-datasource`, uid `json-api`) returned Cloudflare 502 for all 4 cart analytics panels.
- **Symptom**: `Query error: 502` on "Unique Active Carts", "Items in Active Carts", "Stale/Abandoned Carts", "Most Popular Items in Carts".
- **Root cause**: Datasource URL was `http://web:8000` — the monitoring VM (`affordable-gadgets-production-monitoring`, us-east1-b) does NOT run the Django `web` container. The API runs on separate MIG instances. Hostname `web` was unresolvable from Grafana's Docker container, causing connection failure that propagated through Cloudflare Tunnel as 502.
- **Fix**: Changed `url: http://web:8000` → `url: https://api.affordable-gadgetske.com` in both datasource.yml files.
  - `deploy/ansible/roles/monitoring_compose/files/datasource.yml` — Ansible source of truth
  - `deploy/monitoring/grafana/datasources/datasource.yml` — local copy
- The datasource already sends `Authorization: Token ${GF_JSON_API_TOKEN}`, which authenticates against the public API domain.

## Key State

### Topology (confirmed)
- **NO staging environment** — everything is production only
- **All resources in `us-east1-b`**: API MIG instances, monitoring VM, Cloud SQL, Redis
- Monitoring VM (`affordable-gadgets-production-monitoring`) is a **dedicated VM** — does NOT run any Django/API containers
- Prometheus discovers API instances via GCE service discovery (GCP API, not Docker networking)
- Grafana's JSON API datasource now uses the public domain `api.affordable-gadgetske.com`

## Files Modified
- `deploy/ansible/roles/monitoring_compose/files/datasource.yml` — changed JSON API URL
- `deploy/monitoring/grafana/datasources/datasource.yml` — same change (copy)
- `scripts/deploy-monitoring.sh` — added health check + token fetch with retries, `restart grafana`, pass token to renderer
- `scripts/render_monitoring_templates.py` — accept `django_admin_token` arg, pass to grafana.env template
- `.github/workflows/validate-infra.yml` — pass `DJANGO_ADMIN_PASSWORD` secret to deploy step
- `.github/workflows/ci.yml` — add `paths-ignore` so docs-only commits skip API build+deploy

### 3. Grafana JSON API auth failing (400)
- **Error**: After fixing URL, auth token was `{{ django_admin_token | default('admin') }}` literal — renderer never received `django_admin_token` variable.
- **Root cause**: `render_monitoring_templates.py` did not pass `django_admin_token` to the grafana.env template. The CI/CD path always had a broken `GF_JSON_API_TOKEN`.
- **Fix**: `deploy-monitoring.sh` now health-checks the API (3 retries), fetches a fresh DRF token via `POST /api/auth/token/login/` with `DJANGO_ADMIN_PASSWORD` from GitHub secrets (3 retries), passes it to the renderer.
- **New GitHub secret**: `DJANGO_ADMIN_PASSWORD` — the Django admin password. Used only in-memory during CI; never written to disk or transmitted to the VM. Only the token (not the password) ends up in `grafana.env`.

## Deployment
- **Push to deploy** — CI/CD handles everything. Just commit, push, and the pipeline runs the Ansible monitoring playbook against the monitoring VM.
- No manual SSH or Docker commands needed on the monitoring VM.
- The Ansible playbook copies files and restarts services via `docker compose`.

### CI/CD Pipeline Verified (2026-05-19)

| What | Auto-deployed? | Trigger | Mechanism |
|------|---------------|---------|-----------|
| **Monitoring** (datasources, dashboards, Prometheus, Grafana) | ✅ Yes | Push to `main` touching `deploy/` or `scripts/` | `validate-infra.yml` → `deploy-monitoring` job → `scripts/deploy-monitoring.sh` → SCP via IAP tunnel → `docker compose up -d` |
| **Django API** | ✅ Yes | Push to `main` | `ci.yml` → Docker build → Artifact Registry → MIG rolling replace |
| **OpenAPI schema** | ✅ Validate only | PR/push to `main` | `validate-openapi.yml` — comments on PR |
| **Frontends** (Shop, Admin) | ❌ No | Manual Ansible only | No GitHub Actions workflow triggers them |
| **Terraform infrastructure** | ❌ Plan only, no auto-apply | PR touching `deploy/terraform/` | `terraform-plan.yml` — `plan` only. Manual `apply` required. |
| **Rollback** (API) | ❌ Manual | `workflow_dispatch` | `rollback-production.yml` — MIG rolling replace with previous image tag |

## Open Items
- SMTP alerts blocked: `grafana_smtp_user` / `grafana_smtp_password` empty in vault (need Gmail app password)
- Dashboard will show 0 for all period panels until counters are incremented by real user events (or multi-process issue is fixed)
- **Phase 2**: Migrate cart analytics from JSON API panels to Prometheus Gauge metrics for long-term stability (remove dependency on community plugin and direct HTTP to API)

# Session: 2026-05-19 (late) — Dashboard "no data" Investigation

## Verified: Prometheus Stack Is Healthy

### Prometheus scraping all 3 API instances (all UP)
- Instances: `api-7pm1` (10.10.1.32), `api-t60l` (10.10.1.34), `api-v3dh` (10.10.1.19) — all tagged `api`, all in custom VPC `affordable-gadgets-production-vpc`, app subnet.
- Monitoring VM (`affordable-gadgets-production-monitoring`, 10.10.1.33) is in the **same VPC/subnet** → firewall `allow_internal` permits port 8000 traffic ✓
- Prometheus `ag-prometheus` has been running for 10 hours ✓
- GCE service discovery correctly finds and scrapes all 3 API instances every 10s ✓

### Gauges populated in Prometheus (verified via API)
| Metric | Value | Notes |
|--------|-------|-------|
| `inventory_value_total{status="AV"}` | 7,828,909.79 | Real data ✓ |
| `inventory_value_total{status="PP"}` | 254,999.97 | Real data ✓ |
| `carts_total{status="total"}` | 3,800.0 | Real data ✓ |
| `customers_total` | 1.0 | Only 1 customer |
| `leads_total{status="NEW"}` | 1.0 | Only 1 lead |
| `app_instances_active` | 1.0 | Per-worker gauge |
| `active_users` | 0.0 | Redis zset empty (no auth activity within TTL) |
| `revenue_total` | 0.0 | No COMPLETED payments in DB |
| `gross_margin_total` | 0.0 | No sold units |
| `delivery_sla_total` | 0.0 | No delivered orders |

### Counters INVISIBLE to Prometheus (metric not stored)
- `revenue_earned_total`, `leads_created_total`, `leads_converted_total`, `customers_registered_total`, `new_orders_total`, `orders_cancelled_total`, `orders_total`, `payments_total`, `whatsapp_clicks_total`
- These have HELP/TYPE lines in `/metrics/` but **no data samples** → Prometheus never stores them → queries return empty.
- The `or vector(0)` fallback **does work** (`sum(increase(revenue_earned_total[24h])) or vector(0)` returns `0`).
- **Root cause**: Gunicorn multi-process. The worker serving `/metrics/` (`refresh_business_metrics()`) only sets gauge values; counters incremented in other workers are invisible.

### Active Users = 0 — Diagnosis
- `refresh_active_users_metric()` in `inventory/middleware.py:80` checks Redis sorted set `{prefix}:1:active_users_zset`.
- The zset is populated by `RequestTimingMiddleware._record_metrics()` (`middleware.py:156`) on every **authenticated** request.
- If no authenticated request has happened within the TTL (300s), the zset is empty → ZCARD returns 0.
- To get non-zero `active_users`, an authenticated user (e.g., Django admin session) must visit the API within 5 minutes.
- The Redis cache IS configured and reachable (no exceptions logged).

### Known Grafana side-effect: `/react/jsx-runtime` 404
- Logged twice in Grafana logs (user visited `/dashboards`). Not a datasource error.
- Likely a cached panel plugin requesting a resource that doesn't exist in Grafana 11.x.
- Does not affect dashboard rendering or data.

## System Topology (confirmed via gcloud)
```
affordable-gadgets-production-vpc (custom)
├── app subnet (10.10.1.0/24)
│   ├── api-7pm1  (10.10.1.32)  tags: [api, iap-ssh, lb-health-check]
│   ├── api-t60l  (10.10.1.34)  tags: [api, iap-ssh, lb-health-check]
│   ├── api-v3dh  (10.10.1.19)  tags: [api, iap-ssh, lb-health-check]
│   ├── monitoring (10.10.1.33) tags: [iap-ssh, monitoring] ← SA: default compute, cloud-platform scopes
│   ├── admin-* (10.10.1.x)     tags: [admin, iap-ssh, lb-health-check]
│   ├── shop-*  (10.10.1.x)     tags: [shop, iap-ssh, lb-health-check]
│   └── tunnel  (10.10.1.2)     tags: [iap-ssh, tunnel]
└── data subnet
```

## What's Deployed on Monitoring VM
| Container | Status | Port |
|-----------|--------|------|
| `ag-prometheus` | Up 10h | 9090 |
| `ag-grafana` | Up 9m (restarted by deploy) | 3000 |
| `ag-cloudflared` | Up 8m (unhealthy) | tunnel |

## What Dashboard Shows After Fixes
- **Prometheus gauge panels** (inventory, carts, customers, leads, error rate, latency, uptime) → data ✓
- **Prometheus counter panels** (revenue, orders, leads, conversions, customers) → **0** (with `or vector(0)` fallback)
- **JSON API panels** (cart analytics) → data ✓ (URL fixed, token dynamically fetched)
- `$period` template variable works as `interval` type

## Fix: DB-backed cumulative gauges (replacing counters)

### Problem
8 counter metrics (`revenue_earned_total`, `leads_created_total`, `leads_converted_total`, `customers_registered_total`, `new_orders_total`, `orders_cancelled_total`, `orders_total`, `payments_total`) were never stored in Prometheus because gunicorn multi-process prevents cross-worker visibility — `.inc()` calls happen in workers that aren't serving `/metrics/`.

### Solution
Added 8 DB-backed cumulative gauges in `refresh_business_metrics()` (same pattern as the working gauges). These compute cumulative counts from the database every `/metrics/` scrape, bypassing the multi-process issue entirely.

### Files Changed

**Backend: `inventory/observability.py`**
- Added 8 new `Gauge` definitions with `multiprocess_mode="livemostrecent"`:
  - `REVENUE_EARNED_CUMULATIVE` → `revenue_earned`
  - `LEADS_CREATED_CUMULATIVE` → `leads_created`
  - `LEADS_CONVERTED_CUMULATIVE` → `leads_converted`
  - `CUSTOMERS_REGISTERED_CUMULATIVE` → `customers_registered`
  - `ORDERS_CREATED_CUMULATIVE` → `orders_created`
  - `ORDERS_CANCELLED_CUMULATIVE` → `orders_cancelled`
  - `ORDERS_STATUS_CUMULATIVE` → `orders_by_status`
  - `PAYMENTS_CUMULATIVE` → `payments`
- Added `.set()` calls in `refresh_business_metrics()` for all 8, sourcing data from DB:
  - `revenue_earned` = `PesapalPayment.objects.filter(status="COMPLETED").Sum(amount)`
  - `orders_created` = `Order.objects.count()`
  - `orders_cancelled` = `Order.objects.filter(status="Canceled").count()`
  - `orders_by_status` = `Order.objects.filter(status=X).count()` for each status
  - `leads_created` = `Lead.objects.count()`
  - `leads_converted` = `Lead.objects.filter(status="CONVERTED").count()`
  - `customers_registered` = `Customer.objects.distinct().count()` (with orders or leads)
  - `payments` = `PesapalPayment.objects.filter(method=X, status=Y).count()` for each method×status

**Dashboards: `executive-kpi-dashboard.json`** (both copies)
- Replaced all 13 occurrences of old counter metric names with new gauge names across 12 panel queries
- Added new "Carts Total (current)" stat panel: `sum(carts_total{status="total"})` (shows 3,800 carts — real data previously unused)

**Dashboards: `django-dashboard.json`** (both copies)
- `orders_total` → `orders_by_status` (Orders Rate panel)
- `payments_total` → `payments` (Payment Rate panel)

**Config: `deploy/monitoring/prometheus/prometheus.yml`**
- Replaced stale static IPs (`10.10.1.28-30`) with GCE SD config matching the Ansible template

**Config: `deploy/monitoring/docker-compose.monitoring.yml`**
- Added `GF_INSTALL_PLUGINS=marcusolsson-json-datasource` to Grafana environment

### New Dashboard Panel
| Panel | Query | Value |
|---|---|---|
| Carts Total (current) | `sum(carts_total{status="total"})` | 3,800 (real data) |

### Gap Analysis (Post-Fix)
| Layer | Status |
|---|---|
| Backend → Prometheus (gauges with data) | `revenue_earned`, `orders_created`, `orders_cancelled`, `orders_by_status`, `leads_created`, `leads_converted`, `customers_registered`, `payments` — all now populated from DB on each scrape |
| Backend → Prometheus (pre-existing gauges) | `inventory_value_total{AV}=7.8M`, `carts_total{total}=3,800`, `customers_total=1` — unchanged |
| Backend → Prometheus (still 0) | `revenue_total`, `gross_margin_total`, `delivery_sla_total` — no DB data exists |
| Prometheus → Grafana (all panels) | All 8 metric panels now return data from DB-backed gauges instead of 0 |
| Not fixable (no DB data) | `salesperson_performance_total` — no sales data in DB |
