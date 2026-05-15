resource "google_compute_instance" "tunnel" {
  name         = "${var.name_prefix}-tunnel"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["iap-ssh", "tunnel"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    access_config {}
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = var.startup_script

  service_account {
    scopes = ["cloud-platform"]
  }

  allow_stopping_for_update = true
}
