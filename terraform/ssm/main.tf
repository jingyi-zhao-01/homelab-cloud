terraform {
  required_version = ">= 1.5"

  # Partial configuration — bucket/key/region are passed via -backend-config at init time.
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  prefix = "/${var.ssm_path_prefix}"
}

resource "aws_ssm_parameter" "postgres_user" {
  name        = "${local.prefix}/POSTGRES_USER"
  description = "Neon Postgres username for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.postgres_user
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "postgres_password" {
  name        = "${local.prefix}/POSTGRES_PASSWORD"
  description = "Neon Postgres password for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.postgres_password
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "postgres_db" {
  name        = "${local.prefix}/POSTGRES_DB"
  description = "Neon Postgres database name for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.postgres_db
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "database_url" {
  name        = "${local.prefix}/DATABASE_URL"
  description = "Full Neon DATABASE_URL for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.database_url
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "grafana_service_account_token" {
  name        = "${local.prefix}/grafana-service-account-token"
  description = "Grafana service account token for observability agent"
  type        = "SecureString"
  value       = var.grafana_service_account_token
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "llm_api_key" {
  name        = "${local.prefix}/llm-api-key"
  description = "OpenRouter (or compatible) LLM API key for observability agent"
  type        = "SecureString"
  value       = var.llm_api_key
  key_id      = var.kms_key_id

  tags = var.tags
}
