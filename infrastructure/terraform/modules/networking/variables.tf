variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["eu-west-1a", "eu-west-1b"]
}

variable "blocked_ips" {
  description = "CIDR blocks to deny on port 5432 (known scanner/bot IPs). Each entry needs /32 for a single host."
  type        = list(string)
  default     = []
}
