resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "deploy_config" {
  bucket = "${var.name_prefix}-deploy-config-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "deploy_config" {
  bucket = aws_s3_bucket.deploy_config.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "deploy_config" {
  bucket = aws_s3_bucket.deploy_config.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "deploy_config" {
  bucket = aws_s3_bucket.deploy_config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
