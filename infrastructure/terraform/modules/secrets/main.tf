locals {
  prefix = "/${var.project}/${var.environment}"
}

# Random DB password — Terraform manages rotation
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# SSM SecureString parameters — KMS default key (free)
resource "aws_ssm_parameter" "db_password" {
  name  = "${local.prefix}/db_password"
  type  = "SecureString"
  value = random_password.db.result
  tags  = { Name = "${var.project}-db-password" }
}

resource "aws_ssm_parameter" "secret_key" {
  name  = "${local.prefix}/secret_key"
  type  = "SecureString"
  value = var.secret_key
  tags  = { Name = "${var.project}-secret-key" }
}

resource "aws_ssm_parameter" "encryption_key" {
  name  = "${local.prefix}/encryption_key"
  type  = "SecureString"
  value = var.encryption_key
  tags  = { Name = "${var.project}-encryption-key" }
}
