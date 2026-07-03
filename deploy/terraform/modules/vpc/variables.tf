variable "name_prefix" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "public_subnet_cidr" {
  type = string
}

variable "availability_zone" {
  type = string
}

variable "secondary_availability_zone" {
  type    = string
  default = "eu-north-1b"
}

variable "public_subnet_cidr_b" {
  type    = string
  default = "10.0.2.0/24"
}
