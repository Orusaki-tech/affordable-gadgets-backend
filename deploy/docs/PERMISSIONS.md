# Permissions: code vs console

You do **not** need to click through GCP IAM for the platform stack if you use Terraform + scripts.

## Fully automated (Terraform / scripts)

| What | How |
|------|-----|
| GCP APIs (Compute, SQL, Redis, AR, Cloud Build, …) | `deploy/scripts/setup-gcp-apis.sh` or first `migrate-to-platform.sh` |
| VPC, NAT, Cloud SQL, Redis, MIGs, LBs, GCS deploy bucket | `terraform apply -var-file=environments/staging.tfvars` |
| Compute SA → read Artifact Registry + GCS deploy config | `deploy/terraform/deploy_config.tf` |
| GitHub Actions deploy SA + WIF pool/provider | `deploy/terraform/github_wif.tf` (set `github_repository` in tfvars) |
| MIG / instance IAM for platform | `platform.tf` modules |

After apply:

```bash
./deploy/scripts/print-github-secrets.sh
```

Copy outputs into **GitHub repository secrets** (that part is GitHub UI or `gh secret set`, not GCP console).

## One-time on your laptop (not GCP console)

| What | Why |
|------|-----|
| `gcloud auth login` + `gcloud auth application-default login` | Terraform and `gcloud` use your user to create resources |
| `roles/owner` or Editor on project | Your user must be allowed to run `terraform apply` the first time |

Optional: grant yourself IAP SSH to private VMs:

```bash
gcloud projects add-iam-policy-binding gmail-486411 \
  --member="user:YOU@gmail.com" \
  --role="roles/iap.tunnelResourceAccessor"
```

That can be added to Terraform too if you set `var.admin_users` (see below).

## Still manual (not GCP IAM)

| What | Where |
|------|--------|
| **Cloudflare** tunnel token + public hostname → `api_lb_ip` | Cloudflare Zero Trust dashboard (or Cloudflare Terraform provider) |
| **DNS** A records for shop/admin staging | Cloudflare DNS |
| **GitHub secrets** | Repo Settings → Secrets, or `gh secret set` |
| **Ansible vault password** | Local `deploy/ansible/.vault_pass` (not in git) |

## Apply GitHub WIF from code

1. Set repo in `deploy/terraform/environments/staging.tfvars`:

   ```hcl
   github_repository = "your-org/affordable-gadgets-backend"
   ```

2. Apply:

   ```bash
   cd deploy/terraform
   terraform apply -var-file=environments/staging.tfvars
   ```

3. Set GitHub secrets from outputs:

   ```bash
   gh secret set GCP_WIF_PROVIDER --body "$(terraform output -raw gcp_wif_provider)"
   gh secret set GCP_DEPLOY_SA --body "$(terraform output -raw gcp_deploy_sa_email)"
   gh secret set GCP_PROJECT_ID --body "gmail-486411"
   gh secret set GCP_ZONE --body "us-central1-a"
   gh secret set STAGING_API_MIG_NAME --body "$(terraform output -raw api_mig_name)"
   ```

## If something still says “permission denied”

1. Re-run `setup-gcp-apis.sh` (e.g. Cloud Build was added after first migration).
2. `terraform apply` again so new IAM bindings exist.
3. For **private VM SSH**: use IAP (`--tunnel-through-iap`) and `roles/iap.tunnelResourceAccessor` on your user.
4. GitHub deploy SA needs `roles/compute.loadBalancerAdmin` for MIG rolling replace (see `github_wif.tf`).

## Production quota (MIG deploys)

Default trial/small-project limits (~8 `INSTANCES` in `us-east1`, ~12 `CPUS_ALL_REGIONS`) block `max-surge=2` rolls. Use `deploy/scripts/mig-recreate-deploy.sh` (recreate one VM at a time) and keep `min_replicas=1` until you request a quota increase in GCP Console → IAM & admin → Quotas.

Bootstrap API nodes after MIG replace (until startup scripts are fixed):

```bash
./deploy/scripts/bootstrap-api-mig.sh
```

 
