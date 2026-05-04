variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "lambda_packages_bucket" { type = string }
variable "audit_bucket_name" { type = string }
variable "sns_topic_arn" { type = string }
variable "projections_queue_arn" { type = string }
variable "projections_queue_url" { type = string }
variable "ai_analysis_queue_arn" { type = string }
variable "ai_analysis_queue_url" { type = string }
variable "notifications_queue_arn" { type = string }
variable "notifications_queue_url" { type = string }

variable "workers_ec2_public_ip" {
  description = "Elastic IP of the workers EC2 — used to build CELERY_BROKER_URL (Redis)"
  type        = string
  default     = ""
}

variable "database_url" {
  description = "Full PostgreSQL async URL — points to EC2 public IP"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password — also used as Redis requirepass in the broker URL"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  type      = string
  sensitive = true
}

variable "encryption_key" {
  type      = string
  sensitive = true
}
