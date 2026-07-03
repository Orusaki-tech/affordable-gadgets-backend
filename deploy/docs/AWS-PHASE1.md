# AWS Phase 1 — Lean Backend + Monitoring

Deploy Django API + Prometheus/Grafana on AWS **eu-north-1** (~$40–50/month).

## Architecture

- **VPC** `10.0.0.0/16`, single public subnet, no NAT Gateway
- **API EC2** `t3.small` — Docker `ag-api-web` on port 8000
- **Monitoring EC2** `t3.micro` — Prometheus, Grafana, Cloudflare Tunnel
- **RDS** `db.t4g.micro` PostgreSQL 16
- **ECR** `ag-api` + **S3** deploy-config bucket
- **Frontends** stay on Vercel

## Prerequisites

1. AWS CLI configured (`aws sts get-caller-identity` → account `549116505700`)
2. Terraform >= 1.5
3. Docker (local image builds)
4. Ansible + vault (config deploy)
5. Cloudflare Tunnel token for `affordable-gadgetske.com`

## Step 1 — Provision infrastructure

```bash
cd affordable-gadgets-backend
./deploy/scripts/deploy.sh plan
APPLY=1 ./deploy/scripts/deploy.sh apply
```

This creates VPC, EC2, RDS, ECR, S3, IAM roles, and writes `deploy/ansible/vars/generated_from_terraform.yml`.

## Step 2 — Secrets

```bash
cp deploy/ansible/secrets/production.vault.yml.example \
   deploy/ansible/secrets/production.vault.yml

# RDS password from SSM:
aws ssm get-parameter \
  --region eu-north-1 \
  --name "$(terraform -chdir=deploy/terraform output -raw db_password_ssm_parameter)" \
  --with-decryption --query Parameter.Value --output text

# Edit vault: secret_key, db_password, cloudinary, pesapal, cloudflare_tunnel_token,
# grafana_admin_password, django_admin_password

ansible-vault encrypt deploy/ansible/secrets/production.vault.yml
```

## Step 3 — Push API image

```bash
./deploy/scripts/deploy.sh push-image
```

## Step 4 — Deploy API config

```bash
ansible-playbook deploy/ansible/playbooks/api.yml --ask-vault-pass
```

Uploads `api.env` + `docker-compose.api.yml` to S3 and restarts API via SSM.

## Step 5 — Database

### Option A — Fresh database

```bash
./deploy/scripts/deploy.sh migrate
./deploy/scripts/deploy.sh load-blogs
```

### Option B — Migrate from GCP backup

```bash
# From a machine that can reach RDS (SSM port-forward or temporary SG rule):
export RDS_ENDPOINT="$(terraform -chdir=deploy/terraform output -raw rds_endpoint)"
export DB_PASSWORD="..."
./deploy/scripts/migrate-db-to-aws-rds.sh /path/to/backup.sql
```

## Step 6 — Deploy monitoring + tunnel

```bash
export GRAFANA_ADMIN_PASSWORD="..."
export CLOUDFLARE_TUNNEL_TOKEN="..."
export DJANGO_ADMIN_PASSWORD="..."
DEPLOY_TUNNEL_ON_MONITORING=1 ./deploy/scripts/deploy-monitoring.sh
```

## Step 7 — Cloudflare Tunnel routes

In Cloudflare Zero Trust → Tunnels → Public Hostnames:

| Hostname | Service |
|----------|---------|
| `api.affordable-gadgetske.com` | `http://<API_PRIVATE_IP>:8000` |
| `grafana.affordable-gadgetske.com` | `http://localhost:3000` |

Get API private IP:

```bash
terraform -chdir=deploy/terraform output -raw api_private_ip
```

Ensure `api.env` has correct `ALLOWED_HOSTS`, `PESAPAL_IPN_URL`, and CORS origins before cutover.

## Step 8 — Verify

```bash
./deploy/scripts/verify-aws-phase1.sh
```

Manual checks:

- [ ] `GET /health/` → 200
- [ ] Grafana executive KPI dashboard shows inventory data
- [ ] Vercel shop loads products (`NEXT_PUBLIC_API_BASE_URL`)
- [ ] SSM: `aws ssm start-session --target <api-instance-id>`

## Step 9 — GitHub Actions CI/CD

After `terraform apply`, set GitHub repository secrets:

| Secret | Value |
|--------|-------|
| `AWS_ROLE_ARN` | `terraform output github_deploy_role_arn` |
| `AWS_DEPLOY_CONFIG_BUCKET` | terraform output `deploy_config_bucket` |
| `AWS_API_INSTANCE_ID` | terraform output `api_instance_id` |
| `AWS_MONITORING_INSTANCE_ID` | terraform output `monitoring_instance_id` |
| `AWS_API_PRIVATE_IP` | terraform output `api_private_ip` |
| `AWS_RDS_ENDPOINT` | terraform output `rds_endpoint` |
| `AWS_ANSIBLE_VAULT_PASSWORD` | ansible-vault password |

Workflow: [`.github/workflows/deploy-aws.yml`](../../.github/workflows/deploy-aws.yml)

## Access instances (no SSH keys)

```bash
aws ssm start-session \
  --region eu-north-1 \
  --target "$(terraform -chdir=deploy/terraform output -raw api_instance_id)"
```

## Cost controls

- No ALB, NAT Gateway, ElastiCache, or ASG in Phase 1
- Single-AZ RDS; enable Multi-AZ only when needed
- Stop EC2 instances when not testing: AWS Console → EC2 → Stop (RDS still bills)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| SSM agent not online | Wait 2–3 min after instance launch; check IAM instance profile |
| API can't reach RDS | Verify `rds-sg` allows `api-sg` on 5432 |
| Grafana 502 | Check `ag-cloudflared` on monitoring VM; tunnel route to API private IP |
| Health check fails | `docker logs ag-api-web` via SSM; verify `DATABASE_URL` in `api.env` |
| Prometheus empty | Confirm `prometheus.yml` targets API private IP `:8000` |

## Decommission GCP

After 48h stable on AWS:

1. Point all DNS/tunnels to AWS only
2. Snapshot Cloud SQL if needed
3. Delete GCP MIGs, VMs, Cloud SQL, Redis, LBs

## Files

| Path | Purpose |
|------|---------|
| `deploy/terraform/` | Infrastructure as code |
| `deploy/ansible/playbooks/api.yml` | API config deploy |
| `deploy/ansible/playbooks/monitoring.yml` | Monitoring via Ansible+SSM |
| `deploy/scripts/deploy.sh` | Provision + image push + migrate |
| `deploy/scripts/deploy-monitoring.sh` | Monitoring + tunnel deploy |
