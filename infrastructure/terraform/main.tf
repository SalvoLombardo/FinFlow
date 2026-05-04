terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ---------------------------------------------------------------
# Dependency order:
#   secrets → workers_ec2 (db_password)
#   networking → workers_ec2 (subnet + sg)
#   workers_ec2 → compute (public_ip for DATABASE_URL + broker URL)
#   messaging, storage → compute
#   storage → cdn
# ---------------------------------------------------------------

module "secrets" {
  source         = "./modules/secrets"
  project        = var.project
  environment    = var.environment
  db_username    = var.db_username
  secret_key     = var.secret_key
  encryption_key = var.encryption_key
}

module "networking" {
  source             = "./modules/networking"
  project            = var.project
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

module "messaging" {
  source      = "./modules/messaging"
  project     = var.project
  environment = var.environment
  aws_region  = var.aws_region
}

module "storage" {
  source      = "./modules/storage"
  project     = var.project
  environment = var.environment
}

module "cdn" {
  source                          = "./modules/cdn"
  project                         = var.project
  environment                     = var.environment
  frontend_bucket_id              = module.storage.frontend_bucket_id
  frontend_bucket_regional_domain = module.storage.frontend_bucket_regional_domain
}

module "workers_ec2" {
  source                = "./modules/workers_ec2"
  project               = var.project
  environment           = var.environment
  public_subnet_id      = module.networking.public_subnet_ids[0]
  ec2_security_group_id = module.networking.ec2_security_group_id
  sns_topic_arn         = module.messaging.sns_topic_arn
  audit_bucket_arn      = module.storage.audit_bucket_arn
  ssm_prefix            = "/${var.project}/${var.environment}"
  db_username           = var.db_username
  db_password           = module.secrets.db_password
  db_name               = "finflow_db"
  key_public            = file(pathexpand(var.ssh_public_key_path))
}

module "compute" {
  source      = "./modules/compute"
  project     = var.project
  environment = var.environment
  aws_region  = var.aws_region

  lambda_packages_bucket  = module.storage.lambda_packages_bucket_id
  audit_bucket_name       = module.storage.audit_bucket_id
  sns_topic_arn           = module.messaging.sns_topic_arn
  projections_queue_arn   = module.messaging.projections_queue_arn
  projections_queue_url   = module.messaging.projections_queue_url
  ai_analysis_queue_arn   = module.messaging.ai_analysis_queue_arn
  ai_analysis_queue_url   = module.messaging.ai_analysis_queue_url
  notifications_queue_arn = module.messaging.notifications_queue_arn
  notifications_queue_url = module.messaging.notifications_queue_url

  # DATABASE_URL is constructed from the EC2 Elastic IP (known after apply on first run)
  database_url = "postgresql+asyncpg://${var.db_username}:${module.secrets.db_password}@${module.workers_ec2.public_ip}:5432/finflow_db"

  db_password           = module.secrets.db_password
  secret_key            = var.secret_key
  encryption_key        = var.encryption_key
  workers_ec2_public_ip = module.workers_ec2.public_ip
}
