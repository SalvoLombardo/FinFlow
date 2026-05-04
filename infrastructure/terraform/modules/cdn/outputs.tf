output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "Needed for cache invalidation: aws cloudfront create-invalidation --distribution-id ..."
  value       = aws_cloudfront_distribution.frontend.id
}
