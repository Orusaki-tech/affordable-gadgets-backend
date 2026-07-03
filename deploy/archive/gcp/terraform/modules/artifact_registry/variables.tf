variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "repository_ids" {
  type    = list(string)
  default = ["ag-api", "ag-shop", "ag-admin"]
}
