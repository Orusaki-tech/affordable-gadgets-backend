output "api_instance_profile_name" {
  value = aws_iam_instance_profile.api.name
}

output "monitoring_instance_profile_name" {
  value = aws_iam_instance_profile.monitoring.name
}

output "api_role_arn" {
  value = aws_iam_role.api.arn
}

output "monitoring_role_arn" {
  value = aws_iam_role.monitoring.arn
}
