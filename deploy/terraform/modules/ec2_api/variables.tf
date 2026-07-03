variable "name_prefix" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "environment" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "instance_profile_name" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "volume_size_gb" {
  type = number
}

variable "deploy_config_bucket" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}
