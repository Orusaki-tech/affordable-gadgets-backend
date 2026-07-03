# GCP deployment archive

Production moved to **AWS** (`deploy/terraform/`, `deploy/scripts/deploy.sh`) in July 2026.

This folder preserves the former Google Cloud Platform stack for reference only. Do not use these files for new deployments.

## Contents

| Path | Former purpose |
|------|----------------|
| `terraform/` | GCP VPC, MIG, Cloud SQL, Memorystore, Artifact Registry |
| `ansible-playbooks/` | API/shop/admin/monitoring playbooks for GCS + MIG |
| `ansible-inventory/` | Production/staging VM inventories (IAP SSH) |
| `ansible-group-vars/` | GCP project, region, MIG settings |
| `scripts/` | `gcloud`, MIG deploy, Cloud SQL migration, IAP monitoring |
| `workflows/` | GitHub Actions using `google-github-actions` and Cloud SQL |
| `docs/` | WIF setup, permissions, monitoring runbooks, GCP snapshots |
| `deploy-root/` | Legacy single-VM and platform README/scripts |
| `ansible-roles-*` | shop/admin/tunnel/nginx/postgres/django roles for GCP VMs |
| `compose/` | Grafana datasource configs with GCE/Stackdriver auth |

## Active AWS paths

- Infrastructure: `deploy/terraform/`
- Deploy: `deploy/scripts/deploy.sh`, `deploy/scripts/deploy-monitoring.sh`
- Ansible: `deploy/ansible/playbooks/api.yml`, `monitoring.yml`
- CI/CD: `.github/workflows/ci.yml`, `validate-infra.yml`

## Project ID (historical)

`project-07850c05-c54d-486b-80a` — billing disabled June 2026; see `docs/gcp-snapshots/2026-06-20/AUDIT.md`.
