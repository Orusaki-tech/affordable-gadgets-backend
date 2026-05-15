# GitHub Actions → GCP (Workload Identity Federation)

Use WIF so CI can push to Artifact Registry and roll MIGs without JSON keys.

## 1. Create deploy service account

```bash
PROJECT_ID=gmail-486411
SA=platform-deploy
gcloud iam service-accounts create "${SA}" --project="${PROJECT_ID}" \
  --display-name="GitHub platform deploy"

SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/artifactregistry.writer roles/compute.instanceAdmin.v1 \
  roles/iam.serviceAccountUser roles/cloudsql.client; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}"
done
```

## 2. Workload Identity Pool + Provider

```bash
POOL=github
PROVIDER=github-oidc
REPO="YOUR_GITHUB_ORG/affordable-gadgets-backend"   # adjust

gcloud iam workload-identity-pools create "${POOL}" \
  --project="${PROJECT_ID}" --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "${PROVIDER}" \
  --project="${PROJECT_ID}" --location=global \
  --workload-identity-pool="${POOL}" \
  --display-name="GitHub OIDC" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"
```

## 3. GitHub secrets

After `terraform apply`, run:

```bash
./deploy/scripts/print-github-secrets.sh
```

| Secret | Value |
|--------|--------|
| `GCP_WIF_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github-oidc` |
| `GCP_DEPLOY_SA` | `platform-deploy@gmail-486411.iam.gserviceaccount.com` |
| `GCP_PROJECT_ID` | `gmail-486411` |
| `GCP_ZONE` | `us-central1-a` |
| `STAGING_API_MIG_NAME` | from `terraform output api_mig_name` |
| `STAGING_SHOP_MIG_NAME` | from `terraform output shop_mig_name` |
| `CLOUD_SQL_CONNECTION_NAME` | from terraform (migrate job) |
| `STAGING_DATABASE_URL` | after vault/DB ready (optional) |

Repeat MIG names for production with `PRODUCTION_*` when production stack exists.

## 4. Verify

Push to `main` or run **Deploy API staging** workflow. Image should appear in Artifact Registry and MIG rolling update should run.
