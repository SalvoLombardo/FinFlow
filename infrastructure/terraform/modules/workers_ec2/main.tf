locals {
  name = "${var.project}-${var.environment}"
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
    project     = var.project
    db_username = var.db_username
    db_password = var.db_password
    db_name     = var.db_name
  }))

  root_block_device {
    volume_type = "gp2"
    volume_size = 20
  }

  tags = { Name = "${local.name}-workers" }
}

# Elastic IP — free when associated to a running instance
resource "aws_eip" "workers" {
  instance = aws_instance.workers.id
  domain   = "vpc"
  tags     = { Name = "${local.name}-workers-eip" }
}
