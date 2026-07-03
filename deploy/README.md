# Deploy Affordable Gadgets Backend (AWS)

Production runs on **AWS** in `eu-north-1`: EC2 API + monitoring VMs, RDS PostgreSQL, ECR, S3 config bucket, Cloudflare Tunnel.

Legacy GCP tooling is archived under [`archive/gcp/`](archive/gcp/README.md).

## Quick start

```bash
# 1. Provision infrastructure
./deploy/scripts/deploy.sh apply

# 2. Configure secrets
cp deploy/ansible/secrets/production.vault.yml.example \
   deploy/ansible/secrets/production.vault.yml
# Fill in db_password, secret_key, etc., then:
ansible-vault encrypt deploy/ansible/secrets/production.vault.yml

# 3. Deploy API config
ansible-playbook deploy/ansible/playbooks/api.yml --ask-vault-pass

# 4. Deploy monitoring + tunnel
DEPLOY_TUNNEL_ON_MONITORING=1 ./deploy/scripts/deploy-monitoring.sh
```

## CI/CD

| Workflow | Trigger | Action |
|----------|---------|--------|
| `ci.yml` | Push to `main` | Test → ECR push → SSM deploy API → `load_blog_batch` |
| `validate-infra.yml` | Push touching `deploy/` | Validate monitoring configs → deploy monitoring via SSM |

## Key paths

| Path | Purpose |
|------|---------|
| `deploy/terraform/` | VPC, EC2, RDS, ECR, S3, GitHub OIDC |
| `deploy/ansible/playbooks/api.yml` | Render API env + compose → S3 |
| `deploy/ansible/playbooks/monitoring.yml` | Prometheus + Grafana on monitoring EC2 |
| `deploy/scripts/deploy.sh` | Terraform plan/apply, ECR push, migrate, load-blogs |
| `deploy/scripts/deploy-monitoring.sh` | Monitoring stack via SSM |
| `deploy/docs/AWS-PHASE1.md` | Full migration and operations guide |

## GitHub secrets (AWS)

Run `./deploy/scripts/print-github-secrets.sh` after `terraform apply` for the list. Required:

- `AWS_ROLE_ARN`
- `AWS_DEPLOY_CONFIG_BUCKET`
- `AWS_API_INSTANCE_ID`
- `AWS_MONITORING_INSTANCE_ID`
- `AWS_API_PRIVATE_IP`
- `AWS_RDS_ENDPOINT`
- `AWS_ANSIBLE_VAULT_PASSWORD`

## Blog articles

Blog JSON fixtures live in `blog_content/batches/`. On deploy, CI runs:

```bash
docker exec ag-api-web python manage.py load_blog_batch --force
```

To reload manually via SSM, see `scripts/reload-blogs-production.sh`.
