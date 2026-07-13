# Session: 2026-07-03 — AWS production + GCP archive

## Cloud provider
- **AWS** `eu-north-1` — EC2 API (`t3.small`), EC2 monitoring (`t3.small`), RDS PostgreSQL 16, ECR, S3
- **Account:** `549116505700`
- Former GCP stack archived under `deploy/archive/gcp/` (project `project-07850c05-c54d-486b-80a`, billing disabled June 2026)

## Grafana Monitoring
- **URL:** https://monitoring.affordable-gadgetske.com (or grafana.affordable-gadgetske.com)
- **Ingress:** Cloudflare tunnel (`ag-api-cloudflared`) runs on **API EC2**; Grafana backend is monitoring private IP `:3000`
- **Resilience:** t3.small + 2GB swap + on-host watchdog timer + `.github/workflows/monitoring-watchdog.yml` (every 5 min)
- **Dashboard:** "Affordable Gadgets — Marketing Funnel & Users" (uid: `ag-marketing-funnel`)
- **JSON API datasource uid:** `json-api`
- **Auth:** `Authorization: Token ${GF_JSON_API_TOKEN}` from `grafana.env`
- Prometheus scrapes API private IP in VPC (`api_private_ip:8000`)

## Key URLs
| Endpoint | Purpose |
|----------|---------|
| `GET /api/inventory/analytics/datasource-health/` | No-auth health check |
| `GET /api/inventory/analytics/daily-users/` | Today's active users |
| `POST /api/auth/token/login/` | Admin token exchange |

## CI/CD (AWS)
| What | Trigger | Mechanism |
|------|---------|-----------|
| **API** | Push to `main` | `ci.yml` → ECR → S3 config → SSM restart → `load_blog_batch` |
| **Monitoring** | Push touching `deploy/` | `validate-infra.yml` → `deploy/scripts/deploy-monitoring.sh` (SSM) |
| **Terraform** | Manual | `./deploy/scripts/deploy.sh plan\|apply` |

## Blog content
- Fixtures: `blog_content/batches/`
- Load: `python manage.py load_blog_batch --force --create-missing` (tombstones block recreating deleted blogs)
- Batch `038-apple-m5-ai-guide` — M5 AI guide on MacBook/iPad products

## Datasource auth fix
If Grafana panels show 0/empty:
1. Regenerate token: `docker exec ag-api-web python manage.py drf_create_token admin`
2. Update `DJANGO_API_TOKEN` in GitHub secrets
3. Re-run monitoring deploy or push to `deploy/`
