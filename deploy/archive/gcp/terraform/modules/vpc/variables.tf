variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "app_subnet_cidr" {
  type    = string
  default = "10.10.1.0/24"
}

variable "data_subnet_cidr" {
  type    = string
  default = "10.10.2.0/24"
}
