variable "name_prefix" {
  type = string
}

variable "environment" {
  type    = string
  default = ""
}

variable "region" {
  type = string
}

variable "network_id" {
  type = string
}

variable "memory_size_gb" {
  type    = number
  default = 1
}

variable "redis_version" {
  type    = string
  default = "REDIS_7_0"
}
