locals {
  full_name = "${var.name_prefix}-${var.service_name}"
  all_tags  = concat(["lb-health-check", "iap-ssh"], var.tags)
}

resource "google_compute_health_check" "http" {
  name               = "${local.full_name}-hc"
  check_interval_sec = 15
  timeout_sec        = 10

  http_health_check {
    port         = var.port
    request_path = var.health_check_path
  }
}

resource "google_compute_instance_template" "tpl" {
  name_prefix  = "${local.full_name}-"
  machine_type = var.machine_type
  tags         = local.all_tags

  disk {
    source_image = "ubuntu-os-cloud/ubuntu-2204-lts"
    auto_delete  = true
    boot         = true
    disk_size_gb = 30
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    dynamic "access_config" {
      for_each = var.use_external_ip ? [1] : []
      content {}
    }
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = var.startup_script

  service_account {
    scopes = ["cloud-platform"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_compute_region_instance_group_manager" "mig" {
  name   = "${local.full_name}-mig"
  region = var.region

  base_instance_name = local.full_name
  target_size        = var.target_size != null ? var.target_size : var.min_replicas

  # Pin to one zone so fixed max_surge/max_unavailable of 1 is valid (regional MIG rule).
  distribution_policy_zones = var.distribution_policy_zones

  version {
    name              = "primary"
    instance_template = google_compute_instance_template.tpl.id
  }

  named_port {
    name = "http"
    port = var.port
  }

  auto_healing_policies {
    health_check      = google_compute_health_check.http.id
    initial_delay_sec = 300
  }

  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 1
    max_unavailable_fixed = 0
  }
}

resource "google_compute_region_autoscaler" "autoscaler" {
  count  = var.enable_autoscaler && var.target_size == null ? 1 : 0
  name   = "${local.full_name}-as"
  region = var.region
  target = google_compute_region_instance_group_manager.mig.id

  autoscaling_policy {
    min_replicas    = var.min_replicas
    max_replicas    = var.max_replicas
    cooldown_period = 180

    cpu_utilization {
      target = 0.6
    }
    # Enable load_balancing_utilization after MIG is attached to a backend service (see platform.tf).
  }
}
