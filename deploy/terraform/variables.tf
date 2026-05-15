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

# --- Platform (all-in-GCP) ---

variable "platform_enabled" {
  description = "Provision full platform (VPC, Cloud SQL, Redis, MIGs, LBs). When true, legacy single VM is not created."
  type        = bool
  default     = false
}

variable "legacy_mode" {
  description = "When true and platform_enabled is false, create the legacy single GCE instance."
  type        = bool
  default     = true
}

variable "environment" {
  description = "Environment name: staging or production"
  type        = string
  default     = "staging"
}

variable "cloud_sql_tier" {
  type    = string
  default = "db-custom-1-3840"
}

variable "cloud_sql_deletion_protection" {
  type    = bool
  default = false
}

variable "redis_memory_size_gb" {
  type    = number
  default = 1
}

variable "api_machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "api_min_replicas" {
  type    = number
  default = 2
}

variable "api_max_replicas" {
  type    = number
  default = 25
}

variable "shop_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "shop_min_replicas" {
  type    = number
  default = 2
}

variable "shop_max_replicas" {
  type    = number
  default = 40
}

variable "admin_machine_type" {
  type    = string
  default = "e2-small"
}

variable "admin_min_replicas" {
  type    = number
  default = 1
}

variable "admin_max_replicas" {
  type    = number
  default = 5
}

variable "github_wif_enabled" {
  description = "Create GitHub Actions WIF pool + deploy service account (requires github_repositories or github_repository)"
  type        = bool
  default     = true
}

variable "github_repositories" {
  description = "GitHub repos allowed to impersonate deploy SA (org/name each)"
  type        = list(string)
  default     = []
}

variable "github_repository" {
  description = "Deprecated: single repo; use github_repositories. Merged when github_repositories is empty."
  type        = string
  default     = ""
}
