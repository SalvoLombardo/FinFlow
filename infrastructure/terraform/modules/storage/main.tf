locals {
  name = "${var.project}-${var.environment}"
}

# ---------------------------------------------------------------
# Frontend bucket — React SPA served via CloudFront
# ---------------------------------------------------------------

resource "aws_s3_bucket" "frontend" {
  bucket        = "${local.name}-frontend"
  force_destroy = true
  tags = { Name = "${local.name}-frontend" }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration { status = "Enabled" }
}

# ---------------------------------------------------------------
# Audit bucket — Kafka consumer writes JSONL audit logs
# ---------------------------------------------------------------

resource "aws_s3_bucket" "audit" {
  bucket        = "${local.name}-audit-logs"
  force_destroy = false
  tags = { Name = "${local.name}-audit" }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    id     = "archive-to-infrequent-access"
    status = "Enabled"
    filter { prefix = "audit/" }
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}

# ---------------------------------------------------------------
# Lambda packages bucket — CI/CD uploads deployment zips here
# ---------------------------------------------------------------

resource "aws_s3_bucket" "lambda_packages" {
  bucket        = "${local.name}-lambda-packages"
  force_destroy = true
  tags = { Name = "${local.name}-lambda-packages" }
}

resource "aws_s3_bucket_public_access_block" "lambda_packages" {
  bucket                  = aws_s3_bucket.lambda_packages.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "lambda_packages" {
  bucket = aws_s3_bucket.lambda_packages.id
  versioning_configuration { status = "Enabled" }
}
