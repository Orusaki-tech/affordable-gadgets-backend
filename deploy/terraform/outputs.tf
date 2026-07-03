output "aws_region" {
  value = var.aws_region
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "deploy_config_bucket" {
  value = module.s3.bucket_name
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "api_instance_id" {
  value = module.ec2_api.instance_id
}

output "api_private_ip" {
  value = module.ec2_api.private_ip
}

output "monitoring_instance_id" {
  value = module.ec2_monitoring.instance_id
}

output "monitoring_private_ip" {
  value = module.ec2_monitoring.private_ip
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "rds_port" {
  value = module.rds.port
}

output "rds_db_name" {
  value = module.rds.db_name
}

output "rds_username" {
  value = module.rds.username
}

output "db_password_ssm_parameter" {
  value     = module.rds.password_ssm_parameter
  sensitive = true
}

output "github_deploy_role_arn" {
  value = var.github_oidc_enabled ? aws_iam_role.github_deploy[0].arn : ""
}

output "api_image" {
  value = "${module.ecr.repository_url}:production-latest"
}
