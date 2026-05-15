locals {
  full_name = "${var.name_prefix}-${var.service_name}"
}

resource "google_compute_backend_service" "backend" {
  name                  = "${local.full_name}-backend"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 120
  health_checks         = [var.health_check_id]
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = var.instance_group
  }
}

resource "google_compute_url_map" "url_map" {
  name            = "${local.full_name}-url-map"
  default_service = google_compute_backend_service.backend.id
}

resource "google_compute_target_http_proxy" "http" {
  name    = "${local.full_name}-http-proxy"
  url_map = google_compute_url_map.url_map.id
}

resource "google_compute_global_address" "lb_ip" {
  name = "${local.full_name}-lb-ip"
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${local.full_name}-http-fr"
  target                = google_compute_target_http_proxy.http.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}
