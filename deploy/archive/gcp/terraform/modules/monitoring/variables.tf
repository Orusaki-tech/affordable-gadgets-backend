variable "project_id" {
  type = string
}

variable "zone" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "network" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "disk_size_gb" {
  type    = number
  default = 30
}

variable "k6_runner_ip" {
  type        = string
  default     = "0.0.0.0/0"
  description = "Source IP CIDR for Prometheus remote write firewall rule"
}

variable "startup_script" {
  type        = string
  default     = ""
  description = "Startup script for the monitoring VM"
}

