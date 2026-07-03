#!/usr/bin/env bash
# Enable APIs required for platform_enabled=true Terraform apply.
set -euo pipefail

PROJECT_ID="${1:-${GCP_PROJECT_ID:-project-07850c05-c54d-486b-80a}}"

APIS=(
  compute.googleapis.com
  sqladmin.googleapis.com
  redis.googleapis.com
  servicenetworking.googleapis.com
  artifactregistry.googleapis.com
  cloudbuild.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  cloudresourcemanager.googleapis.com
  storage.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
)

echo "Enabling APIs on project ${PROJECT_ID}..."
gcloud services enable "${APIS[@]}" --project="${PROJECT_ID}"
echo "Done."
