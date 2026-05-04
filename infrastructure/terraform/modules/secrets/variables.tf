variable "project" { type = string }
variable "environment" { type = string }
variable "db_username" { type = string }

variable "secret_key" {
  type      = string
  sensitive = true
}

variable "encryption_key" {
  type      = string
  sensitive = true
}
