resource "google_redis_instance" "main" {
  name               = var.environment != "" ? "${var.name_prefix}-${var.environment}-redis" : "${var.name_prefix}-redis"
  tier               = "BASIC"
  memory_size_gb     = var.memory_size_gb
  region             = var.region
  redis_version      = var.redis_version
  authorized_network = var.network_id
}
