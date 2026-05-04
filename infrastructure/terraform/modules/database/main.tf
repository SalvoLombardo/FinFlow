locals {
  name    = "${var.project}-${var.environment}"
  db_name = replace(var.project, "-", "_")
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db-subnet"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${local.name}-db-subnet-group" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.name}-postgres"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t3.micro"

  # Free Tier critical: GP2 (not GP3), 20 GB, no public IP
  storage_type      = "gp2"
  allocated_storage = 20

  db_name  = local.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_security_group_id]
  publicly_accessible    = false

  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name}-final-snapshot"
  deletion_protection       = false

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  multi_az = false

  tags = { Name = "${local.name}-postgres" }
}

# Store full asyncpg connection URL in SSM after RDS endpoint is known
resource "aws_ssm_parameter" "database_url" {
  name  = "${var.ssm_prefix}/database_url"
  type  = "SecureString"
  value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${local.db_name}"
  tags  = { Name = "${var.project}-database-url" }
}
