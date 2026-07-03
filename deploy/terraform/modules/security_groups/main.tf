resource "aws_security_group" "api" {
  name        = "${var.name_prefix}-api-sg"
  description = "API EC2 metrics from monitoring only"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-api-sg"
  }
}

resource "aws_security_group" "monitoring" {
  name        = "${var.name_prefix}-monitoring-sg"
  description = "Monitoring EC2 outbound only Cloudflare tunnel"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-monitoring-sg"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "RDS PostgreSQL API only"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.name_prefix}-rds-sg"
  }
}

resource "aws_security_group_rule" "api_metrics_from_monitoring" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.api.id
  source_security_group_id = aws_security_group.monitoring.id
  description              = "Prometheus scrape from monitoring VM"
}

resource "aws_security_group_rule" "rds_from_api" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.api.id
  description              = "PostgreSQL from API"
}
