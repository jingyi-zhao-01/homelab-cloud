variable "aws_region" {
  description = "AWS region where SSM parameters are created"
  type        = string
  default     = "us-east-1"
}

variable "ssm_path_prefix" {
  description = "SSM parameter path prefix, e.g. 'flashsales/prod'. Parameters are created under /<prefix>/KEY"
  type        = string
  default     = "flashsales/prod"
}

variable "kms_key_id" {
  description = "KMS key ID or alias used to encrypt SecureString parameters. Leave empty to use the AWS-managed default key (alias/aws/ssm)"
  type        = string
  default     = ""
}

variable "postgres_user" {
  description = "Postgres username (sourced from Neon outputs)"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "Postgres password (sourced from Neon outputs)"
  type        = string
  sensitive   = true
}

variable "postgres_db" {
  description = "Postgres database name (sourced from Neon outputs)"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Full DATABASE_URL connection string (sourced from Neon outputs)"
  type        = string
  sensitive   = true
}

variable "redis_url" {
  description = "Full REDIS_URL connection string (sourced from Upstash outputs)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "include_upstash_runtime" {
  description = "Whether to create Upstash-derived SSM parameters for this stack."
  type        = bool
  default     = false
}

variable "include_aiven_kafka_runtime" {
  description = "Whether to create Aiven Kafka-derived SSM parameters for this stack."
  type        = bool
  default     = false
}

variable "upstash_redis_endpoint" {
  description = "Upstash Redis endpoint hostname"
  type        = string
  sensitive   = true
  default     = ""
}

variable "upstash_redis_port" {
  description = "Upstash Redis port"
  type        = string
  default     = ""
}

variable "upstash_redis_password" {
  description = "Upstash Redis password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "upstash_redis_rest_token" {
  description = "Upstash Redis REST token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "upstash_redis_read_only_rest_token" {
  description = "Upstash Redis read-only REST token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_bootstrap_servers" {
  description = "Kafka bootstrap servers for flashsale order-service and order-worker"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_service_uri" {
  description = "Full Kafka service URI"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_security_protocol" {
  description = "Kafka security protocol"
  type        = string
  default     = "SSL"
}

variable "kafka_username" {
  description = "Kafka runtime username"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_password" {
  description = "Kafka runtime password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_access_cert" {
  description = "Kafka runtime client certificate"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_access_key" {
  description = "Kafka runtime client private key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "kafka_terminalization_topic" {
  description = "Primary Kafka topic for order terminalization commands"
  type        = string
  default     = ""
}

variable "kafka_terminalization_retry_topic" {
  description = "Kafka topic for terminalization retry commands"
  type        = string
  default     = ""
}

variable "kafka_terminalization_dlq_topic" {
  description = "Kafka topic for terminalization dead-letter commands"
  type        = string
  default     = ""
}

variable "kafka_terminalization_consumer_group" {
  description = "Kafka consumer group for order terminalization workers"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to all SSM parameters"
  type        = map(string)
  default = {
    project    = "flashsales"
    managed_by = "terraform"
  }
}
