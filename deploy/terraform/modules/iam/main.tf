data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.name_prefix}-api-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role" "monitoring" {
  name               = "${var.name_prefix}-monitoring-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "api_ssm" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "monitoring_ssm" {
  role       = aws_iam_role.monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "api_ec2" {
  statement {
    sid    = "ECRPull"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "S3DeployConfigRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.deploy_config_bucket_arn,
      "${var.deploy_config_bucket_arn}/*",
    ]
  }
}

data "aws_iam_policy_document" "monitoring_ec2" {
  statement {
    sid    = "ECRPull"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "S3DeployConfigRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.deploy_config_bucket_arn,
      "${var.deploy_config_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "EC2DescribeForPrometheus"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "${var.name_prefix}-api-ec2"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_ec2.json
}

resource "aws_iam_role_policy" "monitoring" {
  name   = "${var.name_prefix}-monitoring-ec2"
  role   = aws_iam_role.monitoring.id
  policy = data.aws_iam_policy_document.monitoring_ec2.json
}

resource "aws_iam_instance_profile" "api" {
  name = "${var.name_prefix}-api-ec2"
  role = aws_iam_role.api.name
}

resource "aws_iam_instance_profile" "monitoring" {
  name = "${var.name_prefix}-monitoring-ec2"
  role = aws_iam_role.monitoring.name
}
