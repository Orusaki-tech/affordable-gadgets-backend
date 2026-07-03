output "api_security_group_id" {
  value = aws_security_group.api.id
}

output "monitoring_security_group_id" {
  value = aws_security_group.monitoring.id
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}
