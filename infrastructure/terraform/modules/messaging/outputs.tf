output "sns_topic_arn" {
  value = aws_sns_topic.events.arn
}

output "projections_queue_arn" {
  value = aws_sqs_queue.projections.arn
}

output "projections_queue_url" {
  value = aws_sqs_queue.projections.id
}

output "ai_analysis_queue_arn" {
  value = aws_sqs_queue.ai_analysis.arn
}

output "ai_analysis_queue_url" {
  value = aws_sqs_queue.ai_analysis.id
}

output "notifications_queue_arn" {
  value = aws_sqs_queue.notifications.arn
}

output "notifications_queue_url" {
  value = aws_sqs_queue.notifications.id
}

output "projections_dlq_arn" {
  value = aws_sqs_queue.projections_dlq.arn
}

output "ai_analysis_dlq_arn" {
  value = aws_sqs_queue.ai_analysis_dlq.arn
}

output "notifications_dlq_arn" {
  value = aws_sqs_queue.notifications_dlq.arn
}
