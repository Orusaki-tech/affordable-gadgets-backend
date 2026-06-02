resource "google_compute_instance" "monitoring" {
  name         = "${var.name_prefix}-monitoring"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["iap-ssh", "monitoring"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = var.disk_size_gb
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    # Cloudflare tunnel ingress still targets this legacy alias (grafana.affordable-gadgetske.com).
    alias_ip_range {
      ip_cidr_range = "10.10.1.233/32"
    }
    access_config {
      nat_ip = null
    }
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = var.startup_script

  service_account {
    scopes = ["cloud-platform"]
  }

  allow_stopping_for_update = true

  lifecycle {
    # Startup script is optional; avoid replacing the VM when it is added later.
    ignore_changes = [metadata_startup_script]
  }
}

resource "google_compute_firewall" "allow_prometheus_remote_write" {
  name    = "${var.name_prefix}-allow-prometheus-rw"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["9090"]
  }

  source_ranges = [var.k6_runner_ip]
  target_tags   = ["monitoring"]
}

resource "google_compute_firewall" "allow_grafana_iap_tunnel" {
  name    = "${var.name_prefix}-allow-grafana-iap"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["3000"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["monitoring"]
}
