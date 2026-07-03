#!/usr/bin/env bash
# Restore a PostgreSQL dump into AWS RDS (run from a machine that can reach RDS).
#
# Usage:
#   RDS_ENDPOINT=... DB_PASSWORD=... ./deploy/scripts/migrate-db-to-aws-rds.sh backup.sql
#
# For fresh deploy (no GCP data):
#   ./deploy/scripts/deploy-aws.sh migrate
#   ./deploy/scripts/deploy-aws.sh load-blogs

set -euo pipefail

DUMP_FILE="${1:?Usage: $0 <dump.sql>}"
RDS_ENDPOINT="${RDS_ENDPOINT:?Set RDS_ENDPOINT}"
DB_NAME="${DB_NAME:-affordable_gadgets}"
DB_USER="${DB_USER:-affordable}"
DB_PASSWORD="${DB_PASSWORD:?Set DB_PASSWORD}"

export PGPASSWORD="$DB_PASSWORD"
psql -h "$RDS_ENDPOINT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" >/dev/null
psql -h "$RDS_ENDPOINT" -U "$DB_USER" -d "$DB_NAME" < "$DUMP_FILE"
echo "✓ Restored $DUMP_FILE to $RDS_ENDPOINT"
