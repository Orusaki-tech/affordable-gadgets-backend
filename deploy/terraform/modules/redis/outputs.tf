output "host" {
  value = google_redis_instance.main.host
}

output "port" {
  value = google_redis_instance.main.port
}

output "redis_url" {
  value     = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
  sensitive = false
}
