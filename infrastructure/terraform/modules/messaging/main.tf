locals {
  name = "${var.project}-${var.environment}"
}

# ---------------------------------------------------------------
# SNS Topic — fan-out hub for all FinFlow events
# ---------------------------------------------------------------

resource "aws_sns_topic" "events" {
  name = "${local.name}-events"
  tags = { Name = "${local.name}-events" }
}

# ---------------------------------------------------------------
# Dead Letter Queues (14-day retention)
# ---------------------------------------------------------------

resource "aws_sqs_queue" "projections_dlq" {
  name                      = "${local.name}-projections-dlq"
  message_retention_seconds = 1209600
  tags = { Name = "${local.name}-projections-dlq" }
}

resource "aws_sqs_queue" "ai_analysis_dlq" {
  name                      = "${local.name}-ai-analysis-dlq"
  message_retention_seconds = 1209600
  tags = { Name = "${local.name}-ai-analysis-dlq" }
}

resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${local.name}-notifications-dlq"
  message_retention_seconds = 1209600
  tags = { Name = "${local.name}-notifications-dlq" }
}

# ---------------------------------------------------------------
# Main queues — visibility timeout matches Lambda timeout
# ---------------------------------------------------------------

resource "aws_sqs_queue" "projections" {
  name                       = "${local.name}-projections"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.projections_dlq.arn
    maxReceiveCount     = 3
  })
  tags = { Name = "${local.name}-projections" }
}

resource "aws_sqs_queue" "ai_analysis" {
  name                       = "${local.name}-ai-analysis"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ai_analysis_dlq.arn
    maxReceiveCount     = 3
  })
  tags = { Name = "${local.name}-ai-analysis" }
}

resource "aws_sqs_queue" "notifications" {
  name                       = "${local.name}-notifications"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 3
  })
  tags = { Name = "${local.name}-notifications" }
}

# ---------------------------------------------------------------
# SQS Policies — allow SNS to publish to each queue
# ---------------------------------------------------------------

resource "aws_sqs_queue_policy" "projections" {
  queue_url = aws_sqs_queue.projections.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.projections.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

resource "aws_sqs_queue_policy" "ai_analysis" {
  queue_url = aws_sqs_queue.ai_analysis.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ai_analysis.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.notifications.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events.arn } }
    }]
  })
}

# ---------------------------------------------------------------
# SNS Subscriptions with filter policies (MessageAttributes scope)
# Filter values mirror infrastructure/sns_filter_policies.json
# ---------------------------------------------------------------

resource "aws_sns_topic_subscription" "projections" {
  topic_arn           = aws_sns_topic.events.arn
  protocol            = "sqs"
  endpoint            = aws_sqs_queue.projections.arn
  filter_policy_scope = "MessageAttributes"
  filter_policy = jsonencode({
    event_type = ["budget.updated", "week.closed"]
  })
}

resource "aws_sns_topic_subscription" "ai_analysis" {
  topic_arn           = aws_sns_topic.events.arn
  protocol            = "sqs"
  endpoint            = aws_sqs_queue.ai_analysis.arn
  filter_policy_scope = "MessageAttributes"
  filter_policy = jsonencode({
    event_type = ["ai.analysis.requested", "budget.updated"]
  })
}

resource "aws_sns_topic_subscription" "notifications" {
  topic_arn           = aws_sns_topic.events.arn
  protocol            = "sqs"
  endpoint            = aws_sqs_queue.notifications.arn
  filter_policy_scope = "MessageAttributes"
  filter_policy = jsonencode({
    event_type = ["goal.progress"]
  })
}
