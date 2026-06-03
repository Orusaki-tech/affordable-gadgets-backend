# GitHub Actions → GCP via Workload Identity Federation (no JSON keys).
# Apply with platform; set github_repositories in tfvars (org/name each).

locals {
  github_repos = distinct(concat(
    var.github_repositories,
    var.github_repository != "" ? [var.github_repository] : [],
  ))
  github_wif_enabled = var.platform_enabled && var.github_wif_enabled && length(local.github_repos) > 0
  # GCP account_id max 30 chars; name_prefix + env + "-deploy" can exceed that.
  deploy_sa_id    = "ag-${var.environment}-deploy"
  deploy_sa_email = "${local.deploy_sa_id}@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account" "deploy" {
  count = local.github_wif_enabled ? 1 : 0

  project      = var.project_id
  account_id   = local.deploy_sa_id
  display_name = "GitHub platform deploy (${var.environment})"
}

resource "google_project_iam_member" "deploy_roles" {
  for_each = local.github_wif_enabled ? toset([
    "roles/artifactregistry.writer",
    "roles/compute.instanceAdmin.v1",
    # MIG rolling-action replace reads the attached health check (compute.healthChecks.use).
    "roles/compute.loadBalancerAdmin",
    "roles/iam.serviceAccountUser",
    "roles/cloudsql.client",
    "roles/storage.objectViewer",
  ]) : toset([])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deploy[0].email}"
}

resource "google_iam_workload_identity_pool" "github" {
  count = local.github_wif_enabled ? 1 : 0

  project                   = var.project_id
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = local.github_wif_enabled ? 1 : 0

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository_owner == 'Orusaki-tech'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif" {
  for_each = local.github_wif_enabled ? toset(local.github_repos) : toset([])

  service_account_id = google_service_account.deploy[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${each.value}"
}
