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

resource "aws_ssm_parameter" "redis_url" {
  count = var.redis_url != "" ? 1 : 0

  name        = "${local.prefix}/REDIS_URL"
  description = "Full Upstash REDIS_URL for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.redis_url
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_endpoint" {
  count = var.upstash_redis_endpoint != "" ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_ENDPOINT"
  description = "Upstash Redis endpoint hostname for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_endpoint
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_port" {
  count = var.upstash_redis_port != "" ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_PORT"
  description = "Upstash Redis port for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_port
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_password" {
  count = var.upstash_redis_password != "" ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_PASSWORD"
  description = "Upstash Redis password for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_password
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_rest_token" {
  count = var.upstash_redis_rest_token != "" ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_REST_TOKEN"
  description = "Upstash Redis REST token for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_rest_token
  key_id      = var.kms_key_id

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_read_only_rest_token" {
  count = var.upstash_redis_read_only_rest_token != "" ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_READ_ONLY_REST_TOKEN"
  description = "Upstash Redis read-only REST token for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_read_only_rest_token
  key_id      = var.kms_key_id

  tags = var.tags
}
