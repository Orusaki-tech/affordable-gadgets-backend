output "instance_name" {
  value = google_compute_instance.tunnel.name
}

output "external_ip" {
  value = google_compute_instance.tunnel.network_interface[0].access_config[0].nat_ip
}
