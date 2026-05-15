resource "google_compute_instance" "bastion" {
  name         = "${var.name_prefix}-bastion"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["iap-ssh", "bastion"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 10
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    # No external IP — SSH via IAP only
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  service_account {
    scopes = ["cloud-platform"]
  }

  allow_stopping_for_update = true
}
