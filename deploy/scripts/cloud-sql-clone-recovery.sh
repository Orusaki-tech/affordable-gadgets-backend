#!/usr/bin/env bash
# Guide + helpers for Cloud SQL clone recovery (blogs + inventory units).
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-gmail-486411}"
REGION="${GCP_REGION:-us-east1}"
INSTANCE="${CLOUD_SQL_INSTANCE:-}"

usage() {
  cat <<'EOF'
Cloud SQL clone recovery

  1. List instances and backups:
       ./deploy/scripts/cloud-sql-clone-recovery.sh list

  2. Create a temporary clone (manual step in Console recommended):
       GCP Console → SQL → your instance → Backups → Clone
       Or PITR: Create clone at timestamp BEFORE blog loss / reset_products.

  3. After clone is ready, connect both DBs and audit:
       export DATABASE_URL="postgresql://..."          # current production (via proxy)
       export RESTORE_DATABASE_URL="postgresql://..."  # clone (via proxy, different port)
       python manage.py audit_blog_recovery --compare-restore

  4. Merge from clone (dry run first):
       python manage.py merge_from_restore_db --dry-run
       python manage.py merge_from_restore_db

  5. Fill remaining blogs from repo JSON:
       ./scripts/reload-blogs-production.sh

  6. Delete the clone instance when done (saves cost).

Environment:
  GCP_PROJECT_ID, CLOUD_SQL_INSTANCE (e.g. affordable-gadgets-production-pg)
EOF
}

list_instances() {
  gcloud sql instances list --project="${PROJECT}" --format="table(name,region,databaseVersion,state)"
  echo ""
  if [[ -n "${INSTANCE}" ]]; then
    echo "Backups for ${INSTANCE}:"
    gcloud sql backups list --instance="${INSTANCE}" --project="${PROJECT}" --limit=10 \
      --format="table(id,windowStartTime,status)"
  else
    echo "Set CLOUD_SQL_INSTANCE to list backups for a specific instance."
  fi
}

case "${1:-}" in
  list) list_instances ;;
  -h|--help|help) usage ;;
  *)
    usage
    ;;
esac
