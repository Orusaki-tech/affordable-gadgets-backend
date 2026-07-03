aws_region               = "eu-north-1"
aws_account_id           = "549116505700"
environment              = "production"
name_prefix              = "affordable-gadgets"
availability_zone        = "eu-north-1a"
secondary_availability_zone = "eu-north-1b"
api_instance_type        = "t3.small"
monitoring_instance_type   = "t3.micro"
rds_instance_class       = "db.t4g.micro"
github_oidc_enabled      = true
github_repositories = [
  "Orusaki-tech/affordable-gadgets-backend",
]
