output "api_gateway_url" {
  description = "HTTP API Gateway endpoint — set as REACT_APP_API_URL in the frontend build"
  value       = module.compute.api_gateway_url
}

output "cloudfront_url" {
  description = "CloudFront distribution domain for the React frontend"
  value       = module.cdn.cloudfront_url
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID — needed for cache invalidation in CI/CD"
  value       = module.cdn.cloudfront_distribution_id
}

output "ec2_public_ip" {
  description = "Elastic IP of the workers EC2 — SSH access; also the PostgreSQL and Redis host used by Lambda"
  value       = module.workers_ec2.public_ip
}

output "sns_topic_arn" {
  description = "ARN of the finflow-events SNS topic — set as AWS_SNS_TOPIC_ARN"
  value       = module.messaging.sns_topic_arn
}

output "lambda_packages_bucket" {
  description = "S3 bucket for Lambda deployment packages — CI/CD uploads zips here"
  value       = module.storage.lambda_packages_bucket_id
}

output "frontend_bucket" {
  description = "S3 bucket for the React frontend — CI/CD syncs build output here"
  value       = module.storage.frontend_bucket_id
}

output "audit_bucket" {
  description = "S3 bucket for Kafka audit logs (written by EC2 Celery workers)"
  value       = module.storage.audit_bucket_id
}
