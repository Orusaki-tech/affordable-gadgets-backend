# All-in-GCP platform migration

Target: **MIG + LB + Cloud SQL + Memorystore + Cloudflare Tunnel**. Legacy [deploy-gcp.sh](deploy-gcp.sh) remains for `platform_enabled=false` (single VM).

## One-command staging migration

```bash
# From affordable-gadgets-backend repo root
chmod +x deploy/scripts/*.sh deploy/loadtest/run.sh

# Plan only
./deploy/scripts/migrate-to-platform.sh

# Apply infrastructure (~15–25 min first time)
APPLY=1 ./deploy/scripts/migrate-to-platform.sh --apply
# or: ./deploy/scripts/migrate-to-platform.sh --apply
```

This script:

1. Ensures `deploy/terraform/environments/staging.tfvars` exists (`project_id = gmail-486411`)
2. Enables GCP APIs
3. Runs `terraform apply -var-file=environments/staging.tfvars`
4. Generates `deploy/ansible/vars/generated_from_terraform.yml`
5. Creates `deploy/ansible/secrets/staging.vault.yml` from example (injects DB password when possible)
6. Prints GitHub secrets checklist

## Manual steps (after Terraform)

### 1. Ansible vault

```bash
# Edit secrets, then encrypt
ansible-vault encrypt deploy/ansible/secrets/staging.vault.yml
```

Required: `secret_key`, `cloudflare_tunnel_token`, Cloudinary, Pesapal. `db_password` can come from Terraform (see [init-staging-vault.sh](scripts/init-staging-vault.sh)).

### 2. Database (from legacy VM)

Follow [scripts/migrate-db-to-cloud-sql.md](scripts/migrate-db-to-cloud-sql.md) or:

```bash
./deploy/scripts/migrate-db-to-cloud-sql.sh
```

### 3. First API deploy (GCS → MIG)

Config is stored in GCS (`deploy_config_bucket`); MIG startup pulls `api.env` + compose before starting Docker.

```bash
# Build & push image first (local or CI)
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/gmail-486411/ag-api/ag-api:staging-latest .
docker push us-central1-docker.pkg.dev/gmail-486411/ag-api/ag-api:staging-latest

ansible-playbook -i deploy/ansible/inventory/staging \
  deploy/ansible/playbooks/api.yml \
  -e env_name=staging \
  -e image_tag=staging-latest \
  --ask-vault-pass
```

Shop/admin:

```bash
ansible-playbook -i deploy/ansible/inventory/staging deploy/ansible/playbooks/shop.yml -e image_tag=staging-latest
ansible-playbook -i deploy/ansible/inventory/staging deploy/ansible/playbooks/admin.yml -e image_tag=staging-latest
```

### 4. GitHub Actions

[docs/GITHUB-WIF.md](docs/GITHUB-WIF.md) + `./deploy/scripts/print-github-secrets.sh`

### 5. Cloudflare tunnel

Point `api-staging` origin to **`terraform output api_lb_ip`** — [docs/CLOUDFLARE-TUNNEL-PLATFORM.md](docs/CLOUDFLARE-TUNNEL-PLATFORM.md)

### 6. DNS

[docs/DNS-STAGING.md](docs/DNS-STAGING.md) — shop/admin A records to LB IPs.

### 7. Smoke

```bash
curl -sf https://api-staging.affordable-gadgetske.com/health/
./deploy/loadtest/run.sh smoke
```

## Terraform reference

```bash
cd deploy/terraform
terraform init
terraform plan -var-file=environments/staging.tfvars
terraform apply -var-file=environments/staging.tfvars
../ansible/scripts/generate_ansible_vars_from_terraform.sh
```

| File | Purpose |
|------|---------|
| `environments/staging.tfvars` | Staging values (gitignored) |
| `environments/staging.tfvars.example` | Template |
| `platform.tf` | VPC, SQL, Redis, MIGs, LBs, tunnel |
| `legacy.tf` | Single VM when `platform_enabled=false` |
| `deploy_config.tf` | GCS bucket for compose/env |

## Production

Copy `environments/production.tfvars.example` → `production.tfvars`, raise replicas per [docs/EVENT-RUNBOOK.md](docs/EVENT-RUNBOOK.md), apply, repeat vault/deploy with `env_name=production`.

## Legacy break-glass

```bash
# terraform.tfvars or -var
platform_enabled = false
legacy_mode      = true
```

Then `./deploy/deploy-gcp.sh` works as before.

## SSH (IAP)

```bash
gcloud compute ssh INSTANCE --zone=us-central1-a --tunnel-through-iap --project=gmail-486411
sudo docker exec -it ag-api-web bash
```

## Permissions (code vs console)

See **[docs/PERMISSIONS.md](docs/PERMISSIONS.md)** — most IAM is in Terraform; you only paste GitHub secrets and configure Cloudflare DNS manually.

## Docs index

- [PERMISSIONS.md](docs/PERMISSIONS.md)
- [GITHUB-WIF.md](docs/GITHUB-WIF.md) (manual alternative; prefer `github_wif.tf`)
- [CLOUDFLARE-TUNNEL-PLATFORM.md](docs/CLOUDFLARE-TUNNEL-PLATFORM.md)
- [DNS-STAGING.md](docs/DNS-STAGING.md)
- [migrate-db-to-cloud-sql.md](scripts/migrate-db-to-cloud-sql.md)
- [EVENT-RUNBOOK.md](docs/EVENT-RUNBOOK.md)
- [loadtest/README.md](loadtest/README.md)
