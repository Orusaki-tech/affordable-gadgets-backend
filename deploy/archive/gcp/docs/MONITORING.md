# Monitoring and Observability Stack

## Architecture

```
User ──▶ Cloudflare ──▶ GCP LB ──▶ Django API  ──▶ PostgreSQL
                                      │
                               ┌──────┴──────┐
                               │  /metrics/   │
                               └──────┬──────┘
                                      │ scrape (10s)
                                      ▼
                                  Prometheus ──▶ Grafana
                                      │
                                      ▼
                               AlertManager ──▶ Slack / Email

Sentry SDK (in-app) ──▶ sentry.io (error & performance tracking)
```

## Components

### 1. Prometheus Metrics (`/metrics/`)
Auto-instrumented by `inventory/middleware.py`:
- `http_requests_total` — per method, endpoint, status code
- `http_request_duration_seconds` — histogram by endpoint (p50/p95/p99)
- `orders_total` — per status and payment method
- `payments_total` — per method and status
- `active_users` — gauge for recent user activity
- `cache_hits_total` / `cache_misses_total`

### 2. Sentry Error Tracking
- Catches all unhandled exceptions with full context
- Performance tracing (10% sample by default)
- Profiling (5% sample)
- Configure via `SENTRY_DSN` env var

### 3. Structured JSON Logging
- All logs emitted as newline-delimited JSON to stdout
- Fields: timestamp, level, logger, message, module, function, line, process, thread, exception
- Optional extra fields via `logger.info("msg", extra={"key": "val"})`
- Disable with `JSON_LOGGING=false`

### 4. Grafana Dashboards
Pre-built dashboard `django-dashboard.json`:
- Request rate (total + 5xx)
- Latency percentiles (p50/p95/p99)
- Error rate percentage
- Top endpoints table
- Status code pie chart
- Orders & payment rate
- Active users

## Setup

### Local / Docker Compose
```bash
# Start monitoring stack
docker compose -f deploy/monitoring/docker-compose.monitoring.yml up -d

# Access
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

### Production (GCP)
1. Deploy Prometheus + Grafana to a small GCE VM or GKE
2. Point Prometheus at the MIG's internal LB IP on port 8000, path `/metrics/`
3. (Alternative) Use GCP Cloud Monitoring with the Ops Agent + custom metrics

## Alerts (Recommended)

| Alert | Condition | Action |
|-------|-----------|--------|
| High 5xx rate | `http_requests_total{status=~"5.."} > 1%` for 5m | Check Sentry, rollback if needed |
| High latency | p99 > 2s for 5m | Scale up MIG, check DB |
| Low cache hit rate | `cache_hits / (cache_hits + cache_misses) < 0.5` | Check Redis, warm cache |
| Error spike | Sentry issue count > threshold in 5m | Slack alert, investigate |
| Instance down | `up{job="django"} == 0` for 1m | Check MIG health, restart |

## Env Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | — | Sentry project DSN (enables error tracking) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Performance trace sampling (0–1) |
| `SENTRY_PROFILES_SAMPLE_RATE` | `0.05` | Code profiling sampling (0–1) |
| `JSON_LOGGING` | `true` | JSON-structured logging |
| `OBSERVABILITY_ENABLED` | `true` | Master toggle for observability features |
| `RELEASE_VERSION` | `unknown` | Git SHA or tag for Sentry releases |
