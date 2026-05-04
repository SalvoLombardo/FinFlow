variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "project" {
  description = "Project name used as prefix for all resources"
  type        = string
  default     = "finflow"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to deploy into — keep to minimum to limit Interface Endpoint hourly cost"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b"]
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "finflow"
}

variable "secret_key" {
  description = "JWT signing secret — generate with: openssl rand -hex 32"
  type        = string
  sensitive   = true
}

variable "encryption_key" {
  description = "Fernet key for AI API key encryption — generate with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
  type        = string
  sensitive   = true
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key for EC2 access — generate with: ssh-keygen -t rsa -b 4096 -f ~/.ssh/finflow -N \"\""
  type        = string
  default     = "~/.ssh/finflow.pub"
}
