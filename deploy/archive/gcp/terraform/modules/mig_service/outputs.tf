output "instance_group" {
  value = google_compute_region_instance_group_manager.mig.instance_group
}

output "health_check_id" {
  value = google_compute_health_check.http.id
}

output "instance_template_id" {
  value = google_compute_instance_template.tpl.id
}

output "mig_name" {
  value = google_compute_region_instance_group_manager.mig.name
}
