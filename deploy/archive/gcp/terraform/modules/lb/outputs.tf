output "lb_ip" {
  value = google_compute_global_address.lb_ip.address
}

output "backend_service_id" {
  value = google_compute_backend_service.backend.id
}
