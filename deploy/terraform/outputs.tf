output "instance_name" {
  description = "Name of the GCE instance (for Ansible inventory)"
  value       = google_compute_instance.backend.name
}

output "instance_id" {
  description = "Instance id"
  value       = google_compute_instance.backend.instance_id
}

output "external_ip" {
  description = "External IP of the backend VM (use for Ansible and ALLOWED_HOSTS)"
  value       = google_compute_instance.backend.network_interface[0].access_config[0].nat_ip
}

output "zone" {
  description = "Zone of the instance (short name for gcloud)"
  value       = basename(google_compute_instance.backend.zone)
}

output "project_id" {
  description = "GCP project ID (for gcloud --project)"
  value       = var.project_id
}

# Convenience for Ansible: one-line inventory
output "ansible_inventory_line" {
  description = "Add this to Ansible inventory or use: ansible -i '<external_ip>,' ..."
  value       = google_compute_instance.backend.network_interface[0].access_config[0].nat_ip
}
