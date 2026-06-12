terraform {
  required_version = ">= 1.5"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }

    upstash = {
      source  = "upstash/upstash"
      version = "~> 2.1"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_ssm_parameter" "upstash_email" {
  count = var.upstash_email == "" ? 1 : 0
  name  = var.upstash_email_parameter_name
}

data "aws_ssm_parameter" "upstash_api_key" {
  count           = var.upstash_api_key == "" ? 1 : 0
  name            = var.upstash_api_key_parameter_name
  with_decryption = true
}

locals {
  upstash_provider_email   = var.upstash_email != "" ? var.upstash_email : nonsensitive(data.aws_ssm_parameter.upstash_email[0].value)
  upstash_provider_api_key = var.upstash_api_key != "" ? var.upstash_api_key : data.aws_ssm_parameter.upstash_api_key[0].value
  ssm_prefix               = "/${var.ssm_path_prefix}"
  upstash_redis_rest_url   = "https://${upstash_redis_database.leetcode_intelligence.endpoint}"
}

provider "upstash" {
  email   = local.upstash_provider_email
  api_key = local.upstash_provider_api_key
}

resource "upstash_redis_database" "leetcode_intelligence" {
  database_name  = var.upstash_redis_database_name
  region         = var.upstash_redis_region
  tls            = var.upstash_redis_tls
  eviction       = var.upstash_redis_eviction
  auto_scale     = var.upstash_redis_auto_scale
  primary_region = var.upstash_redis_region == "global" ? var.upstash_redis_primary_region : null
  read_regions   = var.upstash_redis_region == "global" ? var.upstash_redis_read_regions : null
}

resource "aws_ssm_parameter" "upstash_redis_rest_url" {
  name        = "${local.ssm_prefix}/UPSTASH_REDIS_REST_URL"
  description = "Upstash Redis REST URL for leetcode-intelligence rate limiting"
  type        = "SecureString"
  value       = local.upstash_redis_rest_url
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.ssm_tags
}

resource "aws_ssm_parameter" "upstash_redis_rest_token" {
  name        = "${local.ssm_prefix}/UPSTASH_REDIS_REST_TOKEN"
  description = "Upstash Redis REST token for leetcode-intelligence rate limiting"
  type        = "SecureString"
  value       = upstash_redis_database.leetcode_intelligence.rest_token
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.ssm_tags
}

resource "aws_ssm_parameter" "non_admin_rate_limit_max_requests" {
  name        = "${local.ssm_prefix}/NON_ADMIN_RATE_LIMIT_MAX_REQUESTS"
  description = "Per-IP request budget for non-admin leetcode-intelligence traffic"
  type        = "String"
  value       = tostring(var.non_admin_rate_limit_max_requests)
  overwrite   = true

  tags = var.ssm_tags
}

resource "aws_ssm_parameter" "non_admin_rate_limit_window_seconds" {
  name        = "${local.ssm_prefix}/NON_ADMIN_RATE_LIMIT_WINDOW_SECONDS"
  description = "Rate-limit window in seconds for non-admin leetcode-intelligence traffic"
  type        = "String"
  value       = tostring(var.non_admin_rate_limit_window_seconds)
  overwrite   = true

  tags = var.ssm_tags
}
