resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.name_prefix}-db-subnet"
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.name_prefix}-pg"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp3"
  db_name           = var.db_name
  username          = var.db_username
  password          = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 1
  skip_final_snapshot     = var.skip_final_snapshot
  deletion_protection     = var.deletion_protection

  tags = {
    Name = "${var.name_prefix}-pg"
  }
}

resource "aws_ssm_parameter" "db_password" {
  name        = "/ag/${var.environment}/db_password"
  description = "RDS PostgreSQL password for ${var.name_prefix}"
  type        = "SecureString"
  value       = random_password.db.result
}
