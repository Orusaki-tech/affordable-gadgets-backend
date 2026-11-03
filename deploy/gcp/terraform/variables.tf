variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "project-bc0f5694-0e96-4989-861"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-east1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-east1-b"
}

variable "machine_type" {
  description = "GCP machine type"
  type        = string
  default     = "e2-small"
}
