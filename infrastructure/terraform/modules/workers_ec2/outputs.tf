output "public_ip" {
  description = "Elastic IP — SSH access, PostgreSQL host, and Redis host for Lambda"
  value       = aws_eip.workers.public_ip
}

output "instance_id" {
  value = aws_instance.workers.id
}
