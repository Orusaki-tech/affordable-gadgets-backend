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

resource "google_compute_target_https_proxy" "https" {
  count   = var.enable_https ? 1 : 0
  name    = "${local.full_name}-https-proxy"
  url_map = google_compute_url_map.url_map.id
  ssl_certificates = [
    google_compute_managed_ssl_certificate.default[0].id
  ]
}

resource "google_compute_managed_ssl_certificate" "default" {
  count = var.enable_https ? 1 : 0
  name  = "${local.full_name}-ssl-cert"

  managed {
    domains = var.ssl_domains
  }
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

resource "google_compute_global_forwarding_rule" "https" {
  count                 = var.enable_https ? 1 : 0
  name                  = "${local.full_name}-https-fr"
  target                = google_compute_target_https_proxy.https[0].id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}
