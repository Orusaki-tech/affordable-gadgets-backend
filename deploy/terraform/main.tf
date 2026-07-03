locals {
  name_prefix = "${var.name_prefix}-${var.environment}"
}

module "vpc" {
  source = "./modules/vpc"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidr   = var.public_subnet_cidr
  availability_zone    = var.availability_zone
  secondary_availability_zone = var.secondary_availability_zone
  public_subnet_cidr_b = var.public_subnet_cidr_b
}

module "security_groups" {
  source = "./modules/security_groups"

  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
}

module "s3" {
  source = "./modules/s3"

  name_prefix = local.name_prefix
}

module "ecr" {
  source = "./modules/ecr"

  repository_name = var.ecr_repository_name
}

module "iam" {
  source = "./modules/iam"

  name_prefix              = local.name_prefix
  deploy_config_bucket_arn = module.s3.bucket_arn
}

module "rds" {
  source = "./modules/rds"

  name_prefix          = local.name_prefix
  environment          = var.environment
  subnet_ids           = module.vpc.public_subnet_ids
  security_group_id    = module.security_groups.rds_security_group_id
  instance_class       = var.rds_instance_class
  allocated_storage_gb = var.rds_allocated_storage_gb
  db_name              = var.db_name
  db_username          = var.db_username
}

module "ec2_api" {
  source = "./modules/ec2_api"

  name_prefix           = local.name_prefix
  aws_region            = var.aws_region
  environment           = var.environment
  subnet_id             = module.vpc.public_subnet_ids[0]
  security_group_id     = module.security_groups.api_security_group_id
  instance_profile_name = module.iam.api_instance_profile_name
  instance_type         = var.api_instance_type
  volume_size_gb        = var.api_volume_size_gb
  deploy_config_bucket  = module.s3.bucket_name
  ecr_repository_url    = module.ecr.repository_url

  depends_on = [module.rds]
}

module "ec2_monitoring" {
  source = "./modules/ec2_monitoring"

  name_prefix           = local.name_prefix
  environment           = var.environment
  subnet_id             = module.vpc.public_subnet_ids[0]
  security_group_id     = module.security_groups.monitoring_security_group_id
  instance_profile_name = module.iam.monitoring_instance_profile_name
  instance_type         = var.monitoring_instance_type
  volume_size_gb        = var.monitoring_volume_size_gb
  deploy_config_bucket  = module.s3.bucket_name
}
