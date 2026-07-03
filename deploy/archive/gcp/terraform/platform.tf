# All-in-GCP platform: VPC, Cloud SQL, Redis, Artifact Registry, MIGs, LBs, bastion, tunnel.

locals {
  platform_name_prefix = "${var.name_prefix}-${var.environment}"
  deploy_config_bucket = var.platform_enabled ? google_storage_bucket.deploy_config[0].name : ""
  startup_vars = {
    deploy_config_bucket = local.deploy_config_bucket
    environment          = var.environment
  }
  mig_zones = [var.zone, var.secondary_zone]
}

module "vpc" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/vpc"

  project_id  = var.project_id
  region      = var.region
  name_prefix = local.platform_name_prefix
}

module "artifact_registry" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/artifact_registry"

  project_id  = var.project_id
  region      = var.region
  name_prefix = local.platform_name_prefix
}

module "cloud_sql" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/cloud_sql"

  project_id          = var.project_id
  region              = var.region
  name_prefix         = var.environment == "production" ? var.name_prefix : local.platform_name_prefix
  environment         = var.environment == "production" ? "production" : var.environment
  network_id          = module.vpc[0].network_id
  tier                = var.cloud_sql_tier
  deletion_protection = var.cloud_sql_deletion_protection

  depends_on = [module.vpc]
}

module "redis" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/redis"

  name_prefix    = var.environment == "production" ? var.name_prefix : local.platform_name_prefix
  environment    = var.environment == "production" ? "production" : var.environment
  region         = var.region
  network_id     = module.vpc[0].network_id
  memory_size_gb = var.redis_memory_size_gb
}

module "bastion" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/bastion"

  project_id  = var.project_id
  zone        = var.zone
  name_prefix = local.platform_name_prefix
  network     = module.vpc[0].network_name
  subnetwork  = module.vpc[0].app_subnet_name
}

module "monitoring" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/monitoring"

  project_id      = var.project_id
  zone            = var.zone
  name_prefix     = local.platform_name_prefix
  network         = module.vpc[0].network_name
  subnetwork      = module.vpc[0].app_subnet_name
  machine_type    = var.monitoring_machine_type
  disk_size_gb    = var.monitoring_disk_size_gb
  k6_runner_ip    = var.k6_runner_ip
  startup_script  = file("${path.module}/scripts/monitoring-startup.sh.tpl")
}

module "api_mig" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/mig_service"

  project_id                       = var.project_id
  region                           = var.region
  zone                             = var.zone
  name_prefix                      = local.platform_name_prefix
  service_name                     = "api"
  network                          = module.vpc[0].network_name
  subnetwork                       = module.vpc[0].app_subnet_name
  machine_type                     = var.api_machine_type
  tags                             = ["api"]
  port                             = 8000
  health_check_path                = "/health/"
  startup_script                   = templatefile("${path.module}/scripts/api-startup.sh.tpl", local.startup_vars)
  min_replicas                     = var.api_min_replicas
  max_replicas                     = var.api_max_replicas
  enable_autoscaler                = true
  target_size                      = null
  distribution_policy_zones        = local.mig_zones
  autoscaler_cooldown_period       = var.api_autoscaler_cooldown_period
  autoscaler_cpu_target            = var.api_autoscaler_cpu_target
  autoscaler_lb_utilization_target = var.api_autoscaler_lb_utilization_target
}

module "api_lb" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/lb"

  name_prefix          = local.platform_name_prefix
  service_name         = "api"
  port                 = 8000
  instance_group       = module.api_mig[0].instance_group
  health_check_id      = module.api_mig[0].health_check_id
  enable_https         = var.lb_enable_https
  ssl_domains          = var.lb_ssl_domains
  ssl_certificate_name = var.lb_ssl_certificate_name
}

module "shop_mig" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/mig_service"

  project_id                       = var.project_id
  region                           = var.region
  zone                             = var.zone
  name_prefix                      = local.platform_name_prefix
  service_name                     = "shop"
  network                          = module.vpc[0].network_name
  subnetwork                       = module.vpc[0].app_subnet_name
  machine_type                     = var.shop_machine_type
  tags                             = ["shop"]
  port                             = 3000
  health_check_path                = "/"
  startup_script                   = templatefile("${path.module}/scripts/shop-startup.sh.tpl", local.startup_vars)
  min_replicas                     = var.shop_min_replicas
  max_replicas                     = var.shop_max_replicas
  enable_autoscaler                = true
  target_size                      = null
  distribution_policy_zones        = local.mig_zones
  autoscaler_cooldown_period       = var.shop_autoscaler_cooldown_period
  autoscaler_cpu_target            = var.shop_autoscaler_cpu_target
  autoscaler_lb_utilization_target = null
}

module "shop_lb" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/lb"

  name_prefix          = local.platform_name_prefix
  service_name         = "shop"
  port                 = 3000
  instance_group       = module.shop_mig[0].instance_group
  health_check_id      = module.shop_mig[0].health_check_id
  enable_https         = var.lb_enable_https
  ssl_domains          = var.lb_ssl_domains
  ssl_certificate_name = var.lb_ssl_certificate_name
}

module "admin_mig" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/mig_service"

  project_id                       = var.project_id
  region                           = var.region
  zone                             = var.zone
  name_prefix                      = local.platform_name_prefix
  service_name                     = "admin"
  network                          = module.vpc[0].network_name
  subnetwork                       = module.vpc[0].app_subnet_name
  machine_type                     = var.admin_machine_type
  tags                             = ["admin"]
  port                             = 80
  health_check_path                = "/"
  startup_script                   = templatefile("${path.module}/scripts/admin-startup.sh.tpl", local.startup_vars)
  min_replicas                     = var.admin_min_replicas
  max_replicas                     = var.admin_max_replicas
  enable_autoscaler                = true
  target_size                      = null
  distribution_policy_zones        = local.mig_zones
  autoscaler_cooldown_period       = var.admin_autoscaler_cooldown_period
  autoscaler_cpu_target            = var.admin_autoscaler_cpu_target
  autoscaler_lb_utilization_target = null
}

module "admin_lb" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/lb"

  name_prefix          = local.platform_name_prefix
  service_name         = "admin"
  port                 = 80
  instance_group       = module.admin_mig[0].instance_group
  health_check_id      = module.admin_mig[0].health_check_id
  enable_https         = var.lb_enable_https
  ssl_domains          = var.lb_ssl_domains
  ssl_certificate_name = var.lb_ssl_certificate_name
}

module "tunnel" {
  count  = var.platform_enabled ? 1 : 0
  source = "./modules/tunnel"

  project_id     = var.project_id
  zone           = var.zone
  name_prefix    = local.platform_name_prefix
  network        = module.vpc[0].network_name
  subnetwork     = module.vpc[0].app_subnet_name
  startup_script = file("${path.module}/scripts/tunnel-startup.sh.tpl")
}
