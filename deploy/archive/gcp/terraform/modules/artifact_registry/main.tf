resource "google_artifact_registry_repository" "repos" {
  for_each = toset(var.repository_ids)

  location      = var.region
  repository_id = each.value
  description   = "Affordable Gadgets ${each.value}"
  format        = "DOCKER"
}
