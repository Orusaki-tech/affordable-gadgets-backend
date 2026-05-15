variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "service_name" {
  type        = string
  description = "Short name: api, shop, admin"
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

variable "tags" {
  type    = list(string)
  default = []
}

variable "startup_script" {
  type = string
}

variable "port" {
  type = number
}

variable "health_check_path" {
  type    = string
  default = "/"
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 10
}

variable "target_size" {
  type        = number
  default     = null
  description = "If set, fixed MIG size (no autoscaler)"
}

variable "enable_autoscaler" {
  type    = bool
  default = true
}

variable "use_external_ip" {
  type    = bool
  default = false
}

variable "distribution_policy_zones" {
  type        = list(string)
  description = "Zones for regional MIG (single zone avoids multi-zone surge constraints)"
}
