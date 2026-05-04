locals {
  name = "${var.project}-${var.environment}"

  # S3 keys for Lambda packages — CI/CD uploads real zips to these paths
  lambda_s3_keys = {
    api                   = "backend/handler.zip"
    projection_consumer   = "lambda_consumers/projection_consumer.zip"
    ai_consumer           = "lambda_consumers/ai_consumer.zip"
    notification_consumer = "lambda_consumers/notification_consumer.zip"
  }
}

# ---------------------------------------------------------------
# Placeholder zip — uploaded to S3 so terraform apply succeeds
# CI/CD replaces the actual code via aws lambda update-function-code
# ---------------------------------------------------------------

data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"
  source {
    content  = "def handler(event, context):\n    return {'statusCode': 200, 'body': 'Deploying...'}\n"
    filename = "handler.py"
  }
}

resource "aws_s3_object" "placeholder" {
  for_each = local.lambda_s3_keys
  bucket   = var.lambda_packages_bucket
  key      = each.value
  source   = data.archive_file.placeholder.output_path
  etag     = data.archive_file.placeholder.output_md5

  lifecycle {
    # CI/CD will upload real packages — Terraform must not overwrite them
    ignore_changes = [etag, source, source_hash]
  }
}

# ---------------------------------------------------------------
# Shared assume-role policy document
# ---------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------
# Main API Lambda
# ---------------------------------------------------------------

resource "aws_iam_role" "api" {
  name               = "${local.name}-api-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "api_inline" {
  name = "${local.name}-api-inline"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [var.sns_topic_arn]
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name}-api"
  role          = aws_iam_role.api.arn
  runtime       = "python3.12"
  handler       = "app.main.handler"
  timeout       = 30
  memory_size   = 256

  s3_bucket  = var.lambda_packages_bucket
  s3_key     = local.lambda_s3_keys["api"]
  depends_on = [aws_s3_object.placeholder]

  environment {
    variables = {
      DATABASE_URL              = var.database_url
      SECRET_KEY                = var.secret_key
      ENCRYPTION_KEY            = var.encryption_key
      AWS_SNS_TOPIC_ARN         = var.sns_topic_arn
      AWS_SQS_PROJECTIONS_URL   = var.projections_queue_url
      AWS_SQS_AI_ANALYSIS_URL   = var.ai_analysis_queue_url
      AWS_SQS_NOTIFICATIONS_URL = var.notifications_queue_url
      # Redis on EC2 public IP — same instance as PostgreSQL
      CELERY_BROKER_URL       = var.workers_ec2_public_ip != "" ? "redis://:${var.db_password}@${var.workers_ec2_public_ip}:6379/0" : ""
      # Kafka disabled in cloud deployment (insufficient RAM on t2.micro)
      KAFKA_BOOTSTRAP_SERVERS = ""
      KAFKA_AUDIT_TOPIC       = "finflow.audit"
      S3_AUDIT_BUCKET         = var.audit_bucket_name
      ENVIRONMENT             = var.environment
    }
  }

  tags = { Name = "${local.name}-api" }

  lifecycle {
    ignore_changes = [source_code_hash, s3_object_version]
  }
}

# ---------------------------------------------------------------
# projection_consumer Lambda
# ---------------------------------------------------------------

resource "aws_iam_role" "projection_consumer" {
  name               = "${local.name}-projection-consumer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "projection_consumer_logs" {
  role       = aws_iam_role.projection_consumer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "projection_consumer_inline" {
  name = "${local.name}-projection-consumer-inline"
  role = aws_iam_role.projection_consumer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = [var.projections_queue_arn]
    }]
  })
}

resource "aws_lambda_function" "projection_consumer" {
  function_name = "${local.name}-projection-consumer"
  role          = aws_iam_role.projection_consumer.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  timeout       = 300
  memory_size   = 256

  s3_bucket  = var.lambda_packages_bucket
  s3_key     = local.lambda_s3_keys["projection_consumer"]
  depends_on = [aws_s3_object.placeholder]

  environment {
    variables = {
      DATABASE_URL = var.database_url
      ENVIRONMENT  = var.environment
    }
  }

  tags = { Name = "${local.name}-projection-consumer" }

  lifecycle {
    ignore_changes = [source_code_hash, s3_object_version]
  }
}

resource "aws_lambda_event_source_mapping" "projection_consumer" {
  event_source_arn        = var.projections_queue_arn
  function_name           = aws_lambda_function.projection_consumer.arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"]
}

# ---------------------------------------------------------------
# ai_consumer Lambda
# ---------------------------------------------------------------

resource "aws_iam_role" "ai_consumer" {
  name               = "${local.name}-ai-consumer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ai_consumer_logs" {
  role       = aws_iam_role.ai_consumer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "ai_consumer_inline" {
  name = "${local.name}-ai-consumer-inline"
  role = aws_iam_role.ai_consumer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = [var.ai_analysis_queue_arn]
    }]
  })
}

resource "aws_lambda_function" "ai_consumer" {
  function_name = "${local.name}-ai-consumer"
  role          = aws_iam_role.ai_consumer.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  timeout       = 300
  memory_size   = 256

  s3_bucket  = var.lambda_packages_bucket
  s3_key     = local.lambda_s3_keys["ai_consumer"]
  depends_on = [aws_s3_object.placeholder]

  environment {
    variables = {
      DATABASE_URL   = var.database_url
      ENCRYPTION_KEY = var.encryption_key
      ENVIRONMENT    = var.environment
    }
  }

  tags = { Name = "${local.name}-ai-consumer" }

  lifecycle {
    ignore_changes = [source_code_hash, s3_object_version]
  }
}

resource "aws_lambda_event_source_mapping" "ai_consumer" {
  event_source_arn        = var.ai_analysis_queue_arn
  function_name           = aws_lambda_function.ai_consumer.arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
}

# ---------------------------------------------------------------
# notification_consumer Lambda
# ---------------------------------------------------------------

resource "aws_iam_role" "notification_consumer" {
  name               = "${local.name}-notification-consumer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "notification_consumer_logs" {
  role       = aws_iam_role.notification_consumer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "notification_consumer_inline" {
  name = "${local.name}-notification-consumer-inline"
  role = aws_iam_role.notification_consumer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [var.notifications_queue_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_lambda_function" "notification_consumer" {
  function_name = "${local.name}-notification-consumer"
  role          = aws_iam_role.notification_consumer.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  timeout       = 60
  memory_size   = 128

  s3_bucket  = var.lambda_packages_bucket
  s3_key     = local.lambda_s3_keys["notification_consumer"]
  depends_on = [aws_s3_object.placeholder]

  environment {
    variables = {
      DATABASE_URL               = var.database_url
      AWS_NOTIFICATION_TOPIC_ARN = ""
      ENVIRONMENT                = var.environment
    }
  }

  tags = { Name = "${local.name}-notification-consumer" }

  lifecycle {
    ignore_changes = [source_code_hash, s3_object_version]
  }
}

resource "aws_lambda_event_source_mapping" "notification_consumer" {
  event_source_arn        = var.notifications_queue_arn
  function_name           = aws_lambda_function.notification_consumer.arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"]
}

# ---------------------------------------------------------------
# API Gateway HTTP API
# ---------------------------------------------------------------

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"
  description   = "FinFlow HTTP API — proxies all routes to the main Lambda"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }

  tags = { Name = "${local.name}-api" }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
