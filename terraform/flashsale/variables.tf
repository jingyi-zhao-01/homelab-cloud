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
