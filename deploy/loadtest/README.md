# Load testing (k6)

## Target: 2M requests / hour

| Metric | Value |
|--------|--------|
| Total requests | 2,000,000 |
| Window | 1 hour |
| Sustained rate | **556 req/s** (`2_000_000 ÷ 3600`) |

Each iteration in `k6-2m-hour.js` issues **one** HTTP GET (weighted browse mix). At 556 iter/s for 1h you get ~2.0M requests.

## Prerequisites

```bash
brew install k6   # macOS
# https://grafana.com/docs/k6/latest/set-up/install-k6/
chmod +x deploy/loadtest/run.sh
```

## Recommended order

1. **Smoke** (staging, ~2 min):

   ```bash
   ./deploy/loadtest/run.sh smoke
   ```

2. **Ramp** (staging, ~28 min) — find errors before the full hour:

   ```bash
   ./deploy/loadtest/run.sh ramp
   ```

3. **Full soak** (staging first):

   ```bash
   ./deploy/loadtest/run.sh 2m-hour
   ```

4. Shorter production check (coordinate with ops; hits real traffic path):

   ```bash
   DURATION=10m BASE_URL=https://api.affordable-gadgetske.com ./deploy/loadtest/run.sh 2m-hour
   ```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BASE_URL` | `https://api-staging.affordable-gadgetske.com` | API origin |
| `BRAND_CODE` | `AFFORDABLE_GADGETS` | `X-Brand-Code` header |
| `TARGET_RPS` | `556` | Arrival rate (req/s) |
| `DURATION` | `1h` (2m-hour), `2m` (smoke) | Test length |
| `PRE_ALLOCATED_VUS` | auto | k6 VU pool |
| `MAX_VUS` | auto | k6 VU ceiling |

Examples:

```bash
# ~500k requests in 30 minutes
TARGET_RPS=278 DURATION=30m ./deploy/loadtest/run.sh 2m-hour

# Local Django
BASE_URL=http://127.0.0.1:8000 TARGET_RPS=50 ./deploy/loadtest/run.sh smoke
```

## Traffic mix (read-only GET)

- Products list / filtered list (~70%)
- Product detail (~12%)
- Brands, promotions, bundles, health

No cart mutations, auth, or checkout — safe for staging/production catalog paths.

## If one machine cannot sustain 556 req/s

Use multiple k6 processes with execution segments (same `K6_CLOUDEXECUTION_ID` on all):

```bash
# 4 machines × 139 req/s ≈ 556 req/s
for i in 0 1 2 3; do
  k6 run --execution-segment "${i}:1/4" --execution-segment-sequence "0,1,2,3" \
    -e TARGET_RPS=556 -e K6_CLOUDEXECUTION_ID=ag-2m \
    deploy/loadtest/k6-2m-hour.js &
done
wait
```

Or [Grafana Cloud k6](https://grafana.com/products/cloud/k6/) for managed distributed runs.

## Interpreting results

Pass criteria (defaults):

- `http_req_failed` &lt; 1%
- `p(95)` &lt; 3s, `p(99)` &lt; 8s

**Cloudflare** caches many `GET /api/v1/public/products` responses. High cache hit rate lowers origin load; a failed soak may still be fine on event day if cache rules are warm. See [../docs/CLOUDFLARE-CACHE.md](../docs/CLOUDFLARE-CACHE.md).

**Capacity** before a real event: [EVENT-RUNBOOK.md](../docs/EVENT-RUNBOOK.md) (raise `api_min_replicas`, `shop_min_replicas`).

## Scripts

| File | Role |
|------|------|
| `run.sh` | CLI wrapper |
| `k6-smoke.js` | Quick check |
| `k6-ramp.js` | Ramp → hold → ramp down |
| `k6-2m-hour.js` | Sustained 2M/hour profile |
| `k6-browse.js` | Legacy short stage test |
| `lib.js` | Shared mix + config |
