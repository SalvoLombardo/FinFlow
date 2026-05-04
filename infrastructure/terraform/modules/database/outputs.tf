output "endpoint" {
  description = "RDS hostname (without port)"
  value       = aws_db_instance.postgres.address
}

output "port" {
  value = aws_db_instance.postgres.port
}

output "database_url" {
  description = "Full asyncpg connection URL — passed to Lambda env vars"
  value       = aws_ssm_parameter.database_url.value
  sensitive   = true
}

output "database_url_ssm_arn" {
  value = aws_ssm_parameter.database_url.arn
}
