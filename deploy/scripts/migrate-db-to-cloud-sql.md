# Migrate PostgreSQL from legacy VM to Cloud SQL

## Prerequisites

- Platform applied: `platform_enabled=true`, `terraform output cloud_sql_connection_name`
- Legacy VM still running with Docker Postgres
- Local tools: `gcloud`, `cloud-sql-proxy`, `pg_restore`

## Automated script

```bash
./deploy/scripts/migrate-db-to-cloud-sql.sh
```

Environment overrides:

| Variable | Default |
|----------|---------|
| `LEGACY_INSTANCE` | `affordable-gadgets-backend` |
| `LEGACY_ZONE` | `us-central1-a` |
| `LEGACY_PROJECT` | `gmail-486411` |
| `DUMP_LOCAL` | `./affordable_gadgets.dump` |

## Manual steps

### 1. Dump on legacy VM

```bash
gcloud compute ssh affordable-gadgets-backend --zone=us-central1-a --project=gmail-486411
docker exec affordable-gadgets-postgres pg_dump -U affordable -Fc affordable_gadgets > /tmp/affordable_gadgets.dump
exit
gcloud compute scp affordable-gadgets-backend:/tmp/affordable_gadgets.dump ./affordable_gadgets.dump \
  --zone=us-central1-a --project=gmail-486411
```

### 2. Cloud SQL Auth Proxy

```bash
CONN="$(cd deploy/terraform && terraform output -raw cloud_sql_connection_name)"
cloud-sql-proxy "${CONN}" &
sleep 5
export PGPASSWORD="$(cd deploy/terraform && terraform output -raw cloud_sql_db_password)"
```

### 3. Restore

```bash
pg_restore -h 127.0.0.1 -U affordable -d affordable_gadgets --clean --if-exists -Fc affordable_gadgets.dump
```

### 4. Point API at Cloud SQL

Ansible `api.env.j2` uses `cloud_sql_private_ip` from `generated_from_terraform.yml` and `db_password` from vault.

```bash
ansible-playbook -i deploy/ansible/inventory/staging \
  deploy/ansible/playbooks/api.yml -e env_name=staging -e image_tag=staging-latest --ask-vault-pass
```

### 5. Smoke test

```bash
curl -sf "https://api-staging.affordable-gadgetske.com/health/"
curl -sf -H "X-Brand-Code: AFFORDABLE_GADGETS" \
  "https://api-staging.affordable-gadgetske.com/api/v1/public/products/?page_size=1"
```

### 6. Decommission VM Postgres (after cutover)

Only after staging is stable for 24–48h. Keep legacy VM stopped (not deleted) until production is migrated.

## GitHub Actions migrate job

Set repository secrets `CLOUD_SQL_CONNECTION_NAME` and `STAGING_DATABASE_URL`, variable `ENABLE_CLOUD_SQL_MIGRATE=true` to run migrations on deploy (see `.github/workflows/deploy-staging.yml`).
