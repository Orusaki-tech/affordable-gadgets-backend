# Affordable Gadgets Backend - GCP Compute Engine
# Single VM: Django + PostgreSQL (same machine)

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Reserve a static IP (optional; set create_static_ip = true in tfvars)
resource "google_compute_address" "backend" {
  count        = var.create_static_ip ? 1 : 0
  name         = "${var.name_prefix}-ip"
  region       = var.region
  address_type = "EXTERNAL"
}

# Firewall: allow SSH, HTTP, HTTPS
resource "google_compute_firewall" "allow_web" {
  name    = "${var.name_prefix}-allow-web"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.network_tag]
}

# Compute Engine instance (Ubuntu 22.04)
resource "google_compute_instance" "backend" {
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
