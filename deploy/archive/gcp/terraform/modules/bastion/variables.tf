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
  default = "e2-micro"
}
