output "db_password" {
  value     = random_password.db.result
  sensitive = true
}

output "db_password_ssm_arn" {
  value = aws_ssm_parameter.db_password.arn
}

output "secret_key_ssm_arn" {
  value = aws_ssm_parameter.secret_key.arn
}

output "encryption_key_ssm_arn" {
  value = aws_ssm_parameter.encryption_key.arn
}
