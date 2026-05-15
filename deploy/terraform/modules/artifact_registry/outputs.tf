output "registry_host" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}"
}

output "api_image_base" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/ag-api"
}

output "shop_image_base" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/ag-shop"
}

output "admin_image_base" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/ag-admin"
}
