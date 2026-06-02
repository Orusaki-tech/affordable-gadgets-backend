output "instance_name" {
  value = google_compute_instance.monitoring.name
}

output "internal_ip" {
  value = google_compute_instance.monitoring.network_interface[0].network_ip
}
