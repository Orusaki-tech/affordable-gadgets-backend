variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region (e.g. us-central1)"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone within region (e.g. us-central1-a)"
  type        = string
  default     = "us-central1-a"
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "affordable-gadgets-backend"
}

variable "instance_name" {
  description = "Compute Engine instance name"
  type        = string
  default     = "affordable-gadgets-backend"
}

variable "machine_type" {
  description = "GCE machine type (e2-small = 2 vCPU, 2 GB; e2-medium = 2 vCPU, 4 GB)"
  type        = string
  default     = "e2-small"
}

variable "boot_image" {
  description = "Boot disk image (Ubuntu 22.04 LTS)"
  type        = string
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 20
}

variable "network_tag" {
  description = "Network tag for firewall"
  type        = string
  default     = "affordable-gadgets-backend"
}

variable "create_static_ip" {
  description = "Allocate a static external IP"
  type        = bool
  default     = false
}

variable "enable_startup_script" {
  description = "Run a minimal startup script (e.g. install Python for Ansible)"
  type        = bool
  default     = false
}
