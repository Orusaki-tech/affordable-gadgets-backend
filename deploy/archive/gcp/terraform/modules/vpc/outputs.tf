output "network_id" {
  value = google_compute_network.vpc.id
}

output "network_name" {
  value = google_compute_network.vpc.name
}

output "app_subnet_id" {
  value = google_compute_subnetwork.app.id
}

output "app_subnet_name" {
  value = google_compute_subnetwork.app.name
}

output "private_vpc_connection_id" {
  value = google_service_networking_connection.private_vpc_connection.id
}
