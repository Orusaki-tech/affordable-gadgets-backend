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

# VM instance
resource "google_compute_instance" "api" {
  name         = "ag-api"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["http-server", "https-server"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    startup-script = <<-SCRIPT
      #!/bin/bash
      set -e

      # Update system
      apt-get update -y
      apt-get upgrade -y

      # Install Docker
      apt-get install -y apt-transport-https ca-certificates curl software-properties-common
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
      apt-get update -y
      apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

      # Enable Docker
      systemctl enable docker
      systemctl start docker

      # Add ubuntu to docker group
      usermod -aG docker ubuntu

      # Create app directory
      mkdir -p /opt/affordable-gadgets
      chown ubuntu:ubuntu /opt/affordable-gadgets

      # Create PostgreSQL data directory
      mkdir -p /opt/affordable-gadgets/pgdata
      chown 999:999 /opt/affordable-gadgets/pgdata

      echo "VM setup complete at $(date)" > /opt/affordable-gadgets/setup.log
    SCRIPT
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  allow_stopping_for_update = true
}
