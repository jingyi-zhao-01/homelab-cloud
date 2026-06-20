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
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "postgres_password" {
  name        = "${local.prefix}/POSTGRES_PASSWORD"
  description = "Neon Postgres password for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.postgres_password
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "postgres_db" {
  name        = "${local.prefix}/POSTGRES_DB"
  description = "Neon Postgres database name for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.postgres_db
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "database_url" {
  name        = "${local.prefix}/DATABASE_URL"
  description = "Full Neon DATABASE_URL for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.database_url
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "redis_url" {
  count = var.include_upstash_runtime ? 1 : 0

  name        = "${local.prefix}/REDIS_URL"
  description = "Full Upstash REDIS_URL for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.redis_url
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_endpoint" {
  count = var.include_upstash_runtime ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_ENDPOINT"
  description = "Upstash Redis endpoint hostname for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_endpoint
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_port" {
  count = var.include_upstash_runtime ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_PORT"
  description = "Upstash Redis port for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_port
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_password" {
  count = var.include_upstash_runtime ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_PASSWORD"
  description = "Upstash Redis password for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_password
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_rest_token" {
  count = var.include_upstash_runtime ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_REST_TOKEN"
  description = "Upstash Redis REST token for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_rest_token
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "upstash_redis_read_only_rest_token" {
  count = var.include_upstash_runtime ? 1 : 0

  name        = "${local.prefix}/UPSTASH_REDIS_READ_ONLY_REST_TOKEN"
  description = "Upstash Redis read-only REST token for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.upstash_redis_read_only_rest_token
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_bootstrap_servers" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_BOOTSTRAP_SERVERS"
  description = "Kafka bootstrap servers for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_bootstrap_servers
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_service_uri" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_SERVICE_URI"
  description = "Full Kafka service URI for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_service_uri
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_security_protocol" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_SECURITY_PROTOCOL"
  description = "Kafka security protocol for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_security_protocol
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_username" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_USERNAME"
  description = "Kafka runtime username for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_username
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "terraform_data" "kafka_credentials_generation" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  triggers_replace = var.kafka_credentials_generation
}

resource "aws_ssm_parameter" "kafka_password" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_PASSWORD"
  description = "Kafka runtime password for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_password
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags

  lifecycle {
    ignore_changes       = [value]
    replace_triggered_by = [terraform_data.kafka_credentials_generation[0]]
  }
}

resource "aws_ssm_parameter" "kafka_terminalization_topic" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_TERMINALIZATION_TOPIC"
  description = "Kafka primary terminalization topic for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_terminalization_topic
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_terminalization_retry_topic" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_TERMINALIZATION_RETRY_TOPIC"
  description = "Kafka terminalization retry topic for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_terminalization_retry_topic
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_terminalization_dlq_topic" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_TERMINALIZATION_DLQ_TOPIC"
  description = "Kafka terminalization dead-letter topic for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_terminalization_dlq_topic
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}

resource "aws_ssm_parameter" "kafka_terminalization_consumer_group" {
  count = var.include_aiven_kafka_runtime ? 1 : 0

  name        = "${local.prefix}/KAFKA_TERMINALIZATION_CONSUMER_GROUP"
  description = "Kafka terminalization consumer group for ${var.ssm_path_prefix}"
  type        = "SecureString"
  value       = var.kafka_terminalization_consumer_group
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.tags
}
