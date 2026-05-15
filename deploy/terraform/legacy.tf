# Legacy single-VM deployment (Docker + optional local Postgres).
# Disabled when platform_enabled = true.

resource "google_compute_address" "backend" {
  count        = var.platform_enabled || !var.legacy_mode ? 0 : (var.create_static_ip ? 1 : 0)
  name         = "${var.name_prefix}-ip"
  region       = var.region
  address_type = "EXTERNAL"
}

resource "google_compute_firewall" "allow_web_legacy" {
  count   = var.platform_enabled || !var.legacy_mode ? 0 : 1
  name    = "${var.name_prefix}-allow-web"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.network_tag]
}

resource "google_compute_instance" "backend" {
  count        = var.platform_enabled || !var.legacy_mode ? 0 : 1
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.network_tag]

  boot_disk {
    initialize_params {
      image = var.boot_image
      size  = var.boot_disk_size_gb
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = var.create_static_ip ? google_compute_address.backend[0].address : null
    }
  }

  metadata = {
    block-project-ssh-keys = "false"
  }

  metadata_startup_script = var.enable_startup_script ? file("${path.module}/startup.sh.tpl") : null

  service_account {
    scopes = ["cloud-platform"]
  }

  allow_stopping_for_update = true
}
