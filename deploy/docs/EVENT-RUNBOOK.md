# Traffic event runbook (2M requests / hour)

Target: **~556 req/s** sustained for 1 hour (2,001,600 HTTP GETs). See [../loadtest/README.md](../loadtest/README.md).

## T-24h

- [ ] `terraform apply` with raised `api_min_replicas=6`, `shop_min_replicas=8` in production.tfvars
- [ ] Verify Cloudflare cache rules ([CLOUDFLARE-CACHE.md](CLOUDFLARE-CACHE.md))
- [ ] Staging soak: `./deploy/loadtest/run.sh ramp` then `./deploy/loadtest/run.sh 2m-hour` against staging
- [ ] Production validation (optional, short): `DURATION=5m TARGET_RPS=556 ./deploy/loadtest/run.sh 2m-hour` with `BASE_URL=https://api.affordable-gadgetske.com`
- [ ] Freeze deploys except hotfixes

## T-1h

- [ ] Confirm all MIG instances healthy
- [ ] `curl https://api.affordable-gadgetske.com/health/`
- [ ] Confirm Redis hit rate / no DB connection errors in logs

## During

- [ ] Watch LB 5xx and MIG size in Cloud Console
- [ ] If 5xx > 1%: enable Attack Mode, purge cache if stale catalog

## Rollback

- GitHub Actions: **Rollback API production** with previous SHA
- DB: Cloud SQL PITR (manual, not in CI)
