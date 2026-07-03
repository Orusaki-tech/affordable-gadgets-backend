# Blog and inventory recovery

Blogs were lost when `reset_products` deleted all products (articles cascaded). Recovery uses:

1. **Repo JSON** — `blog_content/batches/` via `load_blog_batch`
2. **Optional DB restore** — `merge_from_restore_db` when `RESTORE_DATABASE_URL` points at a backup

## Quick recovery (production on AWS)

```bash
./scripts/reload-blogs-production.sh
```

Or push to `main` — CI runs `load_blog_batch --force` after each API deploy.

## Local with RDS

```bash
export DATABASE_URL="postgresql://user:pass@<rds-endpoint>:5432/affordable_gadgets?sslmode=require"
export DJANGO_SETTINGS_MODULE=store.settings_production
export SECRET_KEY=local-only
export ALLOWED_HOSTS=localhost
export FRONTEND_BASE_URL=https://shop.affordable-gadgetske.com

python manage.py load_blog_batch --dry-run
python manage.py load_blog_batch --force
```

## Optional merge from backup database

```bash
export RESTORE_DATABASE_URL="postgresql://...@host:5432/affordable_gadgets"
python manage.py audit_blog_recovery --compare-restore
python manage.py merge_from_restore_db --dry-run
python manage.py merge_from_restore_db
./scripts/reload-blogs-production.sh
```

## Commands reference

| Command | Purpose |
|---------|---------|
| `audit_blog_recovery` | Count products/articles/units; JSON slug gaps |
| `audit_blog_recovery --compare-restore` | Diff vs `RESTORE_DATABASE_URL` |
| `merge_from_restore_db` | Copy missing articles + units (slug rules) |
| `load_blog_batch --force` | Reload all JSON fixtures |

## Monitoring

Redeploy dashboards via push to `deploy/` (triggers `validate-infra.yml`) or:

```bash
DEPLOY_TUNNEL_ON_MONITORING=1 ./deploy/scripts/deploy-monitoring.sh
```

## Historical GCP recovery

Cloud SQL clone workflows and scripts are archived under `deploy/archive/gcp/`.
