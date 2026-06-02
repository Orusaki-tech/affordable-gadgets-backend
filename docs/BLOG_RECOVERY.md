# Blog and inventory recovery

Blogs were lost when `reset_products` deleted all products (articles cascaded). Recovery uses:

1. **Repo JSON** — `blog_content/batches/` (311 files) via `load_blog_batch`
2. **Cloud SQL clone** — optional merge via `merge_from_restore_db` when `RESTORE_DATABASE_URL` points at a backup clone

## Quick recovery (GitHub Actions)

1. Push this branch to `main` (includes migration `0061_productarticle_protect`).
2. Actions → **Recover blogs (production)** → Run workflow.
3. Optional: set secret `RESTORE_DATABASE_URL` to the clone connection string and enable **merge_from_restore_db** in the workflow input.

## Local / CI with Cloud SQL Proxy

```bash
export CLOUD_SQL_CONNECTION_NAME="project:region:instance"
export PRODUCTION_DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/affordable_gadgets"
export DATABASE_URL="$PRODUCTION_DATABASE_URL"
export DJANGO_SETTINGS_MODULE=store.settings_production
export SECRET_KEY=local-only
export ALLOWED_HOSTS=localhost
export FRONTEND_BASE_URL=https://shop.affordable-gadgetske.com

./scripts/reload-blogs-production.sh
```

## Cloud SQL clone (optional, for DB-sourced articles + units)

```bash
./deploy/scripts/cloud-sql-clone-recovery.sh list
# Create clone in GCP Console (Backups → Clone or PITR)

export RESTORE_DATABASE_URL="postgresql://...@127.0.0.1:5433/affordable_gadgets"  # second proxy port
python manage.py audit_blog_recovery --compare-restore
python manage.py merge_from_restore_db --dry-run
python manage.py merge_from_restore_db
./scripts/reload-blogs-production.sh  # fills gaps from JSON
```

## On a running API VM (image includes blog_content/)

```bash
./scripts/deploy-blogs.sh
```

## Commands reference

| Command | Purpose |
|---------|---------|
| `audit_blog_recovery` | Count products/articles/units; JSON slug gaps |
| `audit_blog_recovery --compare-restore` | Diff vs `RESTORE_DATABASE_URL` |
| `merge_from_restore_db` | Copy missing articles + units (slug rules) |
| `load_blog_batch --force` | Reload all JSON fixtures |

## Monitoring

Historical Prometheus TSDB is usually **not** recoverable after VM/volume loss. Dashboards in git redeploy via:

- Actions → **Recover monitoring stack**, or
- `./scripts/deploy-monitoring.sh`

Check volume size: `./deploy/scripts/check-monitoring-data.sh`
