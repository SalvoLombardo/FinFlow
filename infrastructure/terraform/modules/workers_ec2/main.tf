locals {
  name = "${var.project}-${var.environment}"
}

data "aws_region" "current" {}

# ---------------------------------------------------------------
# CloudWatch Logs — PostgreSQL connection log (visibility into the public-DB
# exposure: who's connecting/failing auth). Docker's awslogs driver ships
# container stdout/stderr here directly — no CloudWatch Agent needed.
# Short retention + the always-free CloudWatch Logs allowance (5 GB
# ingestion/storage, 10 custom metrics, 10 alarms) keep this at $0 for a
# personal-scale app. See PRODUCTION_READINESS.md "public Postgres" finding.
# ---------------------------------------------------------------

resource "aws_cloudwatch_log_group" "postgres" {
  name              = "/${local.name}/postgres"
  retention_in_days = 14
  tags              = { Name = "${local.name}-postgres-logs" }
}

resource "aws_cloudwatch_log_metric_filter" "postgres_failed_auth" {
  name           = "${local.name}-postgres-failed-auth"
  log_group_name = aws_cloudwatch_log_group.postgres.name
  pattern        = "\"password authentication failed\""

  metric_transformation {
    name      = "PostgresFailedAuthAttempts"
    namespace = "${local.name}/Postgres"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_sns_topic" "security_alerts" {
  name = "${local.name}-security-alerts"
  tags = { Name = "${local.name}-security-alerts" }
}

resource "aws_cloudwatch_metric_alarm" "postgres_failed_auth" {
  alarm_name          = "${local.name}-postgres-failed-auth"
  alarm_description   = "Repeated PostgreSQL authentication failures — possible brute-force against the publicly-reachable instance."
  namespace           = aws_cloudwatch_log_metric_filter.postgres_failed_auth.metric_transformation[0].namespace
  metric_name         = aws_cloudwatch_log_metric_filter.postgres_failed_auth.metric_transformation[0].name
  statistic           = "Sum"
  period              = 600
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
  ok_actions          = [aws_sns_topic.security_alerts.arn]
}

# Kafka audit producer emits this metric when all 3 retries are exhausted and an
# audit event is permanently dropped. Any non-zero value in a 5-minute window is
# a data-integrity event worth investigating — fire on ≥1 drop.
resource "aws_cloudwatch_metric_alarm" "kafka_audit_dropped" {
  alarm_name          = "${local.name}-kafka-audit-dropped"
  alarm_description   = "One or more Kafka audit events were permanently dropped after all retries. Audit log has a gap."
  namespace           = "FinFlow/Audit"
  metric_name         = "DroppedAuditEvents"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

# ---------------------------------------------------------------
# IAM role for EC2 workers
# ---------------------------------------------------------------

resource "aws_iam_role" "workers" {
  name = "${local.name}-workers-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# SSM Session Manager — SSH-less access to the instance
resource "aws_iam_role_policy_attachment" "workers_ssm" {
  role       = aws_iam_role.workers.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "workers_inline" {
  name = "${local.name}-workers-inline"
  role = aws_iam_role.workers.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [var.sns_topic_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = ["${var.audit_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = ["arn:aws:ssm:*:*:parameter${var.ssm_prefix}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = ["${aws_cloudwatch_log_group.postgres.arn}:*"]
      },
      {
        # cloudwatch:PutMetricData does not support resource-level restrictions —
        # Resource = ["*"] is required by the AWS API for this action.
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "workers" {
  name = "${local.name}-workers-profile"
  role = aws_iam_role.workers.name
}

# ---------------------------------------------------------------
# SSH key pair
# ---------------------------------------------------------------

resource "aws_key_pair" "workers" {
  key_name   = "${local.name}-key"
  public_key = var.key_public
}

# ---------------------------------------------------------------
# Latest Amazon Linux 2023 AMI
# ---------------------------------------------------------------

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---------------------------------------------------------------
# EC2 instance — t3.micro (Free Tier eligible in eu-west-1)
# ---------------------------------------------------------------

resource "aws_instance" "workers" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.micro"
  key_name               = aws_key_pair.workers.key_name
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [var.ec2_security_group_id]
  iam_instance_profile   = aws_iam_instance_profile.workers.name

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    project        = var.project
    environment    = var.environment
    aws_region     = data.aws_region.current.name
    db_username    = var.db_username
    db_password    = var.db_password
    db_name        = var.db_name
    log_group_name = aws_cloudwatch_log_group.postgres.name
  }))

  root_block_device {
    volume_type = "gp2"
    volume_size = 20
  }

  tags = { Name = "${local.name}-workers" }

  lifecycle {
    # data.aws_ami resolves to "most recent" at plan time — without this, every
    # apply after Amazon publishes a newer al2023 image would replace the running
    # instance (destroying Postgres/Redis/Celery; no separate EBS volume backs the
    # DB, so this would mean data loss). Pin to whatever AMI is already running;
    # bump deliberately (with a backup/migration plan) when an OS upgrade is wanted.
    ignore_changes = [ami]
  }
}

# Elastic IP — free when associated to a running instance
resource "aws_eip" "workers" {
  instance = aws_instance.workers.id
  domain   = "vpc"
  tags     = { Name = "${local.name}-workers-eip" }
}
