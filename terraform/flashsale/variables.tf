variable "neon_api_key" {
  description = "Neon API key — create one at console.neon.tech → Account Settings → API Keys"
  type        = string
  sensitive   = true
}

variable "neon_region" {
  description = "Neon region id (https://neon.tech/docs/introduction/regions)"
  type        = string
  default     = "aws-us-east-1"
}

variable "neon_history_retention_seconds" {
  description = "Point-in-time restore retention in seconds; 21600 is compatible with the current Neon plan limit"
  type        = number
  default     = 21600
}

variable "grafana_url" {
  description = "Base URL of the Grafana instance."
  type        = string
}

variable "grafana_auth" {
  description = "Grafana provider auth string, typically an API token."
  type        = string
  sensitive   = true
}

variable "grafana_folder_title" {
  description = "Grafana folder title for flashsale dashboards."
  type        = string
  default     = "Flashsale"
}

variable "grafana_folder_uid" {
  description = "Stable Grafana folder UID for flashsale dashboards."
  type        = string
  default     = "flashsale-folder"
}

variable "flashsale_namespace" {
  description = "Kubernetes namespace where flashsale services run."
  type        = string
  default     = "flashsales"
}

variable "neon_datasource_uid" {
  description = "Grafana datasource UID for the Neon-backed PostgreSQL datasource used by flashsale."
  type        = string
}

variable "loki_datasource_uid" {
  description = "Grafana datasource UID for the Loki logs datasource."
  type        = string
}

variable "tempo_datasource_uid" {
  description = "Grafana datasource UID for the Tempo traces datasource."
  type        = string
}

variable "prometheus_datasource_uid" {
  description = "Grafana datasource UID for the Prometheus datasource that scrapes Aiven Kafka metrics."
  type        = string
  default     = "prometheus"
}

variable "processing_sla_minutes" {
  description = "Minutes after which a processing task is treated as stuck."
  type        = number
  default     = 5
}

variable "aws_region" {
  description = "AWS region where flashsale SSM parameters are created."
  type        = string
  default     = "us-west-1"
}

variable "ssm_path_prefix" {
  description = "SSM parameter path prefix, e.g. 'flashsales/prod'. Parameters are created under /<prefix>/KEY."
  type        = string
  default     = "flashsales/prod"
}

variable "kms_key_id" {
  description = "KMS key ID or alias used to encrypt SecureString parameters. Leave empty to use the AWS-managed default key."
  type        = string
  default     = ""
}

variable "ssm_tags" {
  description = "Tags applied to all flashsale SSM parameters."
  type        = map(string)
  default = {
    project    = "flashsales"
    managed_by = "terraform"
  }
}

variable "upstash_email" {
  description = "Optional direct override for the Upstash account email used by the Terraform provider. Leave empty to read from SSM."
  type        = string
  default     = ""
}

variable "upstash_api_key" {
  description = "Optional direct override for the Upstash API key used by the Terraform provider. Leave empty to read from SSM."
  type        = string
  sensitive   = true
  default     = ""
}

variable "upstash_email_parameter_name" {
  description = "SSM parameter name containing the Upstash account email for provider bootstrap."
  type        = string
  default     = "/upstash/email"
}

variable "upstash_api_key_parameter_name" {
  description = "SSM parameter name containing the Upstash API key for provider bootstrap."
  type        = string
  default     = "/upstash/api_key"
}

variable "upstash_redis_database_name" {
  description = "Logical database name for flashsale Redis."
  type        = string
  default     = "flashsale"
}

variable "upstash_redis_region" {
  description = "Upstash Redis topology selector. Upstash now expects global databases; pair this with primary_region."
  type        = string
  default     = "global"
}

variable "upstash_redis_primary_region" {
  description = "Primary region when upstash_redis_region is set to global."
  type        = string
  default     = "us-west-1"
}

variable "upstash_redis_read_regions" {
  description = "Optional read replica regions when upstash_redis_region is global."
  type        = set(string)
  default     = []
}

variable "upstash_redis_tls" {
  description = "Whether to require TLS for the Upstash Redis endpoint."
  type        = bool
  default     = true
}

variable "upstash_redis_eviction" {
  description = "Whether to enable eviction when the Upstash database reaches its max size."
  type        = bool
  default     = false
}

variable "upstash_redis_auto_scale" {
  description = "Whether Upstash should automatically upgrade the Redis plan when quotas are reached."
  type        = bool
  default     = false
}

variable "upstash_redis_budget" {
  description = "Monthly budget in USD for the flashsale Upstash Redis database."
  type        = number
  default     = 20
}

variable "aiven_api_token" {
  description = "Optional direct override for the Aiven API token used by the Terraform provider. Leave empty to read from SSM."
  type        = string
  sensitive   = true
  default     = ""
}

variable "aiven_api_token_parameter_name" {
  description = "SSM SecureString parameter name containing the Aiven API token for provider bootstrap."
  type        = string
  default     = "/avien/api_token"
}

variable "aiven_project_name" {
  description = "Aiven project name that Terraform manages for flashsale Kafka resources."
  type        = string
  default     = "flashsale"
}

variable "aiven_project_parent_id" {
  description = "Optional direct override for the Aiven organization or organizational unit ID under which the flashsale project is created. Leave empty to read from SSM."
  type        = string
  default     = ""
}

variable "aiven_org_id_parameter_name" {
  description = "SSM SecureString parameter name containing the Aiven organization or organizational unit ID for project creation."
  type        = string
  default     = "/avien/org_id"
}

variable "aiven_kafka_service_name" {
  description = "Aiven Kafka service name for flashsale terminalization."
  type        = string
  default     = "flashsale-kafka"
}

variable "aiven_kafka_plan" {
  description = "Aiven Kafka plan. free-0 is Aiven's free tier."
  type        = string
  default     = "free-0"
}

variable "aiven_kafka_cloud_name" {
  description = "Optional explicit Aiven cloud name for the Kafka service. In CI, leave empty to auto-resolve a project-accessible cloud that supports the selected Kafka plan."
  type        = string
  default     = ""
}

variable "aiven_kafka_version" {
  description = "Kafka major version for the Aiven service. Aiven free-0 currently requires 4.1 or newer."
  type        = string
  default     = "4.1"
}

variable "aiven_kafka_termination_protection" {
  description = "Whether to prevent accidental deletion of the Aiven Kafka service."
  type        = bool
  default     = true
}

variable "aiven_kafka_topic_termination_protection" {
  description = "Whether to prevent accidental deletion of Aiven Kafka topics."
  type        = bool
  default     = true
}

variable "aiven_kafka_order_service_username" {
  description = "Kafka user name used by flashsale order-service and order-worker."
  type        = string
  default     = "flashsale-order-service"
}

variable "aiven_kafka_topic_partitions" {
  description = "Partition count for each flashsale Kafka terminalization topic. Aiven free tier allows up to two partitions per topic."
  type        = number
  default     = 2
}

variable "aiven_kafka_topic_replication" {
  description = "Replication factor for flashsale Kafka terminalization topics. For free-0, this must be at least 2."
  type        = number
  default     = 2
}

variable "aiven_kafka_terminalization_retention_ms" {
  description = "Retention in milliseconds for the primary terminalization topic."
  type        = number
  default     = 86400000
}

variable "aiven_kafka_terminalization_retry_retention_ms" {
  description = "Retention in milliseconds for the terminalization retry topic."
  type        = number
  default     = 86400000
}

variable "aiven_kafka_terminalization_dlq_retention_ms" {
  description = "Retention in milliseconds for the terminalization dead-letter topic."
  type        = number
  default     = 86400000
}

variable "kafka_terminalization_topic" {
  description = "Primary Kafka topic for order terminalization commands."
  type        = string
  default     = "flashsale.order.terminalization.v1"
}

variable "kafka_terminalization_retry_topic" {
  description = "Kafka topic for terminalization retry commands."
  type        = string
  default     = "flashsale.order.terminalization.retry.v1"
}

variable "kafka_terminalization_dlq_topic" {
  description = "Kafka topic for terminalization dead-letter commands."
  type        = string
  default     = "flashsale.order.terminalization.dlq.v1"
}

variable "kafka_terminalization_consumer_group" {
  description = "Kafka consumer group used by the flashsale order terminalization worker."
  type        = string
  default     = "flashsale-order-terminalization-worker"
}
