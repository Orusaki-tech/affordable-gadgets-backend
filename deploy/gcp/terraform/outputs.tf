output "instance_name" {
  description = "Name of the VM instance"
  value       = google_compute_instance.api.name
}

output "instance_zone" {
  description = "Zone of the VM instance"
  value       = google_compute_instance.api.zone
}

output "instance_external_ip" {
  description = "External IP of the VM instance"
  value       = google_compute_instance.api.network_interface[0].access_config[0].nat_ip
}

output "instance_internal_ip" {
  description = "Internal IP of the VM instance"
  value       = google_compute_instance.api.network_interface[0].network_ip
}
