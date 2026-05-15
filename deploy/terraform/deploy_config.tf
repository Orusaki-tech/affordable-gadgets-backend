# GCS bucket for api.env / docker-compose files — MIG startup pulls these on boot.

resource "google_storage_bucket" "deploy_config" {
  count = var.platform_enabled ? 1 : 0

  name                        = "${local.platform_name_prefix}-deploy-config"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = var.environment == "staging"

  versioning {
    enabled = true
  }
}

# Default compute SA (used by GCE/MIG unless a custom SA is set) can read deploy configs.
data "google_project" "current" {
  count      = var.platform_enabled ? 1 : 0
  project_id = var.project_id
}

resource "google_storage_bucket_iam_member" "deploy_config_compute_reader" {
  count = var.platform_enabled ? 1 : 0

  bucket = google_storage_bucket.deploy_config[0].name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_project.current[0].number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_artifact_registry_reader" {
  count = var.platform_enabled ? 1 : 0

  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${data.google_project.current[0].number}-compute@developer.gserviceaccount.com"
}
