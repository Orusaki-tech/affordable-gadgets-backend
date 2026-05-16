# Traffic Event Runbook (2M requests / hour)

Target: **~556 req/s** sustained for 1 hour (2,001,600 HTTP GETs).
See [../loadtest/README.md](../loadtest/README.md).

## Pre-Event Checklist

### T-48h
- [ ] Set `SENTRY_DSN` in production env (create Sentry project if needed)
- [ ] Deploy monitoring stack (Prometheus + Grafana)
- [ ] Run k6 smoke test: `DURATION=2m TARGET_RPS=100 ./deploy/loadtest/run.sh 2m-hour`
- [ ] Verify Grafana dashboard shows live request rate, latency, and error data
- [ ] Set up Slack alerts in Grafana for 5xx > 1% and p99 > 2s
- [ ] Confirm Sentry is receiving events (trigger a test error via admin)

### T-24h
- [ ] `terraform apply` with raised `api_min_replicas=6`, `shop_min_replicas=8` in production.tfvars
- [ ] Verify Cloudflare cache rules ([CLOUDFLARE-CACHE.md](CLOUDFLARE-CACHE.md))
- [ ] Staging soak: `./deploy/loadtest/run.sh ramp` then `./deploy/loadtest/run.sh 2m-hour` against staging
- [ ] Production validation (optional, short): `DURATION=5m TARGET_RPS=556 ./deploy/loadtest/run.sh 2m-hour`
- [ ] Freeze deploys except hotfixes
- [ ] **Observability check**: Confirm all metrics flowing to Grafana, Sentry healthy

### T-1h
- [ ] Confirm all MIG instances healthy
- [ ] `curl https://api.affordable-gadgetske.com/health/` → `{"status":"ok"}`
- [ ] `curl https://api.affordable-gadgetske.com/metrics/` → prometheus output
- [ ] Check Grafana: request rate baseline, p50 latency, active users
- [ ] Confirm Redis hit rate / no DB connection errors in Sentry

### T-0 (Start)
- [ ] Begin traffic; start k6 or go-live with event traffic

## During Event

### Real-Time Monitoring Dashboard
**Open Grafana → Django API - Event Monitoring**
- Watch **Error Rate (%)** panel — if > 1%, investigate immediately
- Watch **P99 Latency** — if > 2s, auto-scaling may need help
- Watch **Request Rate** — confirms target is hit
- **Top Endpoints** table — shows which endpoints are under most load

### Sentinel Playbook

| Symptom | Probable Cause | Action |
|---------|---------------|--------|
| 5xx rate > 1% | Code bug, DB overload, resource exhaustion | 1. Check Sentry for latest errors<br>2. Check Cloud SQL CPU/connections<br>3. Rollback via GH Actions if needed |
| p99 > 2s | DB slow queries, missing indexes, cache miss | 1. Check Sentry performance traces<br>2. Check Redis cache hit rate<br>3. Manually increase MIG size |
| Request rate flat / dropping | Cloudflare issues, DNS, LB problems | 1. Check Cloudflare dashboard<br>2. Check LB backend health<br>3. Verify MIG instances > 0 |
| Sentry error spike | New bug introduced, external API failure | 1. Check Sentry issue details<br>2. Identify failing endpoint<br>3. Rollback or hotfix |
| High active users but low orders | Payment flow issue | 1. Check Pesapal/M-Pesa metrics<br>2. Look for payment errors in Sentry |

## Rollback
- GitHub Actions: **Rollback API production** with previous SHA
- DB: Cloud SQL PITR (manual, not in CI)
- After rollback: verify /metrics/ endpoint returns data, Sentry reports stable

## Post-Event
- [ ] Generate post-event report from Grafana (export PDF of dashboard)
- [ ] Review Sentry issues — prioritise fixes by frequency
- [ ] Check Cloud SQL and Redis metrics for capacity planning
- [ ] Save k6 load test results for baseline comparison
- [ ] Update auto-scaling thresholds based on observed performance
