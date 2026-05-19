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
