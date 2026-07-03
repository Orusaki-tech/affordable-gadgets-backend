output "bucket_name" {
  value = aws_s3_bucket.deploy_config.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.deploy_config.arn
}
