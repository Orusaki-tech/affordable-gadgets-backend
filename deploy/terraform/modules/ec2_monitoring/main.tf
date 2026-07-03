data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "monitoring" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.instance_profile_name

  user_data = templatefile("${path.module}/../../scripts/monitoring-user-data.sh.tpl", {
    deploy_config_bucket = var.deploy_config_bucket
    environment          = var.environment
  })

  root_block_device {
    volume_size = var.volume_size_gb
    volume_type = "gp3"
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  tags = {
    Name    = "${var.name_prefix}-monitoring"
    Service = "monitoring"
  }

  lifecycle {
    ignore_changes = [ami]
  }
}
