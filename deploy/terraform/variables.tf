variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
  default     = "549116505700"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "affordable-gadgets"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.0.1.0/24"
}

variable "availability_zone" {
  type    = string
  default = "eu-north-1a"
}

variable "secondary_availability_zone" {
  type    = string
  default = "eu-north-1b"
}

variable "public_subnet_cidr_b" {
  type    = string
  default = "10.0.2.0/24"
}

variable "api_instance_type" {
  type    = string
  default = "t3.small"
}

variable "monitoring_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "api_volume_size_gb" {
  type    = number
  default = 20
}

variable "monitoring_volume_size_gb" {
  type    = number
  default = 20
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "rds_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "affordable_gadgets"
}

variable "db_username" {
  type    = string
  default = "affordable"
}

variable "ecr_repository_name" {
  type    = string
  default = "ag-api"
}

variable "github_repositories" {
  description = "GitHub repos allowed to assume the deploy role (org/repo)"
  type        = list(string)
  default     = ["Orusaki-tech/affordable-gadgets-backend"]
}

variable "github_oidc_enabled" {
  description = "Create GitHub Actions OIDC provider and deploy role"
  type        = bool
  default     = true
}
