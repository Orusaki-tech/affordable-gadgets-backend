# Session: 2026-09-28 — GCP production

## Cloud provider
- **GCP** is production (API + shop). Region `us-east1` / zone `us-east1-b`.
- **API VM:** `35.237.10.17` (SSH user `shwariaccessories`), app root `/opt/affordable-gadgets`
- **Project (active):** `project-bc0f5694-0e96-4989-861` — see `deploy/gcp/terraform/`
- **Shop:** Artifact Registry `us-east1-docker.pkg.dev/.../ag-shop/ag-shop` + production MIG (`scripts/mig-recreate-deploy.sh`)
- Public API: `https://api.affordable-gadgetske.com` · Shop: `https://www.affordable-gadgetske.com`
- Older GCP project `project-07850c05-c54d-486b-80a` and AWS notes under `deploy/archive/` are **historical only** — do not treat them as live production.

## Grafana Monitoring
- **URL:** https://monitoring.affordable-gadgetske.com (or grafana.affordable-gadgetske.com)
- **Auth:** `Authorization: Token ${GF_JSON_API_TOKEN}` from `grafana.env`
- **Dashboard:** "Affordable Gadgets — Marketing Funnel & Users" (uid: `ag-marketing-funnel`)
- **JSON API datasource uid:** `json-api`
- Prefer querying Django over the private/API-container URL from the monitoring host, not only the public Cloudflare URL

## Key URLs
| Endpoint | Purpose |
|----------|---------|
| `GET /api/inventory/analytics/datasource-health/` | No-auth health check |
| `GET /api/inventory/analytics/daily-users/` | Today's active users |
| `POST /api/auth/token/login/` | Admin / Studio token exchange |

## CI/CD (GCP)
| What | Trigger | Mechanism |
|------|---------|-----------|
| **API** | Push to `main` | `.github/workflows/deploy-gcp.yml` — tests, then SSH to API VM → `git fetch` + `docker compose build/up` |
| **Shop (frontend)** | Push to `main` | `affordable-gadgets-frontend` `.github/workflows/ci.yml` — build image → Artifact Registry → MIG recreate |
| **Terraform (GCP)** | Manual | `deploy/gcp/terraform/` (`project-bc0f5694-0e96-4989-861`) |

Shop deploy needs GCP billing enabled on the Artifact Registry project. If push fails with “billing must be enabled”, fix billing before Studio/storefront UI changes reach production.

## Blog content
- Fixtures: `blog_content/batches/`
- Load only when intentional: `./deploy/scripts/deploy.sh load-blogs` or `python manage.py load_blog_batch --force --create-missing`
- Deleted blogs are tombstoned and will not be recreated by the loader
- Batch `038-apple-m5-ai-guide` — M5 AI guide on MacBook/iPad products

## Studio curation notes
- Homepage Featured products / videos / blogs are **tag-driven** (`Featured`, `Video` on products; `Featured` on articles)
- Studio Remove uses `POST /api/inventory/products/{id}/remove_tags/` (by name/slug) so clears stick
- Public `featured=1` / `homepage_videos=1` do **not** invent untagged fallbacks

## Datasource auth fix
If Grafana panels show **Datasource Reachable / Auth Token Valid = Unreachable**:
1. Confirm `GF_JSON_API_TOKEN` in monitoring `grafana.env` is valid (create via `drf_create_token` on the API container)
2. Update `DJANGO_API_TOKEN` / related GitHub secrets and redeploy monitoring
3. Point the Infinity datasource at the reachable private/API URL, not a broken public path
4. Deploy refuses `placeholder` tokens — monitoring deploy should fail loudly if auth is broken
