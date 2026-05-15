# Legacy outputs (when legacy VM exists)

output "instance_name" {
  description = "Name of the legacy GCE instance"
  value       = try(google_compute_instance.backend[0].name, null)
}

output "instance_id" {
  description = "Legacy instance id"
  value       = try(google_compute_instance.backend[0].instance_id, null)
}

output "external_ip" {
  description = "External IP of the legacy backend VM"
  value       = try(google_compute_instance.backend[0].network_interface[0].access_config[0].nat_ip, null)
}

output "zone" {
  description = "Zone of the instance"
  value       = var.zone
}

output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "ansible_inventory_line" {
  description = "Legacy Ansible inventory line"
  value       = try(google_compute_instance.backend[0].network_interface[0].access_config[0].nat_ip, null)
}

# Platform outputs

output "cloud_sql_private_ip" {
  value     = try(module.cloud_sql[0].private_ip_address, null)
  sensitive = false
}

output "cloud_sql_connection_name" {
  value = try(module.cloud_sql[0].connection_name, null)
}

output "redis_host" {
  value = try(module.redis[0].host, null)
}

output "redis_port" {
  value = try(module.redis[0].port, null)
}

output "redis_url" {
  value     = try(module.redis[0].redis_url, null)
  sensitive = false
}

output "artifact_registry_host" {
  value = try(module.artifact_registry[0].registry_host, null)
}

output "api_lb_ip" {
  value = try(module.api_lb[0].lb_ip, null)
}

output "shop_lb_ip" {
  value = try(module.shop_lb[0].lb_ip, null)
}

output "admin_lb_ip" {
  value = try(module.admin_lb[0].lb_ip, null)
}

output "api_mig_name" {
  value = try(module.api_mig[0].mig_name, null)
}

output "bastion_name" {
  value = try(module.bastion[0].instance_name, null)
}

output "tunnel_instance_name" {
  value = try(module.tunnel[0].instance_name, null)
}

output "tunnel_external_ip" {
  value = try(module.tunnel[0].external_ip, null)
}

output "deploy_config_bucket" {
  value = try(google_storage_bucket.deploy_config[0].name, null)
}

output "cloud_sql_db_password" {
  value     = try(module.cloud_sql[0].db_password, null)
  sensitive = true
}

output "shop_mig_name" {
  value = try(module.shop_mig[0].mig_name, null)
}

output "admin_mig_name" {
  value = try(module.admin_mig[0].mig_name, null)
}

output "github_secrets_hint" {
  description = "Map these to GitHub Actions secrets after apply (run deploy/scripts/print-github-secrets.sh)"
  value = var.platform_enabled ? {
    GCP_PROJECT_ID            = var.project_id
    GCP_ZONE                  = var.zone
    GCP_WIF_PROVIDER          = try(google_iam_workload_identity_pool_provider.github[0].name, null)
    GCP_DEPLOY_SA             = try(google_service_account.deploy[0].email, null)
    STAGING_API_MIG_NAME      = try(module.api_mig[0].mig_name, null)
    STAGING_SHOP_MIG_NAME     = try(module.shop_mig[0].mig_name, null)
    STAGING_ADMIN_MIG_NAME    = try(module.admin_mig[0].mig_name, null)
    CLOUD_SQL_CONNECTION_NAME = try(module.cloud_sql[0].connection_name, null)
  } : null
}

output "gcp_wif_provider" {
  description = "GitHub secret GCP_WIF_PROVIDER"
  value       = try(google_iam_workload_identity_pool_provider.github[0].name, null)
}

output "gcp_deploy_sa_email" {
  description = "GitHub secret GCP_DEPLOY_SA"
  value       = try(google_service_account.deploy[0].email, null)
}
