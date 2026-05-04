output "frontend_bucket_id" {
  value = aws_s3_bucket.frontend.id
}

output "frontend_bucket_regional_domain" {
  value = aws_s3_bucket.frontend.bucket_regional_domain_name
}

output "audit_bucket_id" {
  value = aws_s3_bucket.audit.id
}

output "audit_bucket_arn" {
  value = aws_s3_bucket.audit.arn
}

output "lambda_packages_bucket_id" {
  value = aws_s3_bucket.lambda_packages.id
}

output "lambda_packages_bucket_arn" {
  value = aws_s3_bucket.lambda_packages.arn
}
