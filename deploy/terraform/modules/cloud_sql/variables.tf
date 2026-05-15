variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "network_id" {
  type = string
}

variable "database_version" {
  type    = string
  default = "POSTGRES_16"
}

variable "tier" {
  type    = string
  default = "db-custom-1-3840"
}

variable "db_name" {
  type    = string
  default = "affordable_gadgets"
}

variable "db_user" {
  type    = string
  default = "affordable"
}

variable "deletion_protection" {
  type    = bool
  default = false
}
