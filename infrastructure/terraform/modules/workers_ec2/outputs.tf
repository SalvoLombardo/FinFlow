output "public_ip" {
  description = "Elastic IP — SSH access, PostgreSQL host, and Redis host for Lambda"
  value       = aws_eip.workers.public_ip
}

output "instance_id" {
  value = aws_instance.workers.id
}

output "security_alerts_topic_arn" {
  description = <<-EOT
    SNS topic that receives the PostgreSQL repeated-failed-auth CloudWatch alarm.
    Subscribe your email after apply (Terraform can't complete an email subscription —
    it requires a confirmation click):
      aws sns subscribe --topic-arn <this-arn> --protocol email --notification-endpoint you@example.com
  EOT
  value       = aws_sns_topic.security_alerts.arn
}
