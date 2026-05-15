# Monitoring and alerts (GCP)

## Cloud Monitoring alerts (recommended)

| Alert | Condition |
|-------|-----------|
| LB 5xx rate | Backend 5xx > 1% for 5m |
| MIG unhealthy | Unhealthy instances > 0 for 5m |
| Cloud SQL connections | > 80% max connections |
| Cloud SQL CPU | > 85% for 10m |
| Redis down | Memorystore uptime check fails |

## Dashboards

- MIG instance count, CPU, LB request rate
- Cloud SQL queries/sec, connections
- API latency from Ops Agent logs

## Logs

- `gcloud logging read` filtered by `resource.type=gce_instance`
- Django errors: search `severity>=ERROR`

## Event runbook

1. Raise `api_min_replicas` / `shop_min_replicas` in [environments/production.tfvars](../terraform/environments/production.tfvars) and `terraform apply`
2. Enable Cloudflare Attack Mode
3. Extend cache TTL on public product list
4. Rollback: [rollback-production.yml](../../.github/workflows/rollback-production.yml)
