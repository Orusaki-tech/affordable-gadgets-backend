variable "name_prefix" {
  type = string
}

variable "service_name" {
  type = string
}

variable "port" {
  type = number
}

variable "instance_group" {
  type = string
}

variable "health_check_id" {
  type = string
}

variable "enable_https" {
  type    = bool
  default = false
}
