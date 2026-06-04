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

variable "grafana_service_account_token" {
  description = "Grafana service account token for observability agent"
  type        = string
  sensitive   = true
}

variable "llm_api_key" {
  description = "OpenRouter (or compatible) LLM API key for observability agent"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags applied to all SSM parameters"
  type        = map(string)
  default = {
    project    = "flashsales"
    managed_by = "terraform"
  }
}
