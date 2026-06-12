variable "aws_region" {
  description = "AWS region where leetcode-intelligence SSM parameters are created."
  type        = string
  default     = "us-west-1"
}

variable "ssm_path_prefix" {
  description = "SSM parameter path prefix. Parameters are created under /<prefix>/KEY."
  type        = string
  default     = "leetcode-intelligence"
}

variable "kms_key_id" {
  description = "KMS key ID or alias used to encrypt SecureString parameters. Leave empty to use the AWS-managed default key."
  type        = string
  default     = ""
}

variable "ssm_tags" {
  description = "Tags applied to all leetcode-intelligence SSM parameters."
  type        = map(string)
  default = {
    project    = "leetcode-intelligence"
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
  description = "Logical database name for leetcode-intelligence rate limiting."
  type        = string
  default     = "leetcode-intelligence-rate-limit"
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
  description = "Monthly budget in USD for the leetcode-intelligence Upstash Redis database."
  type        = number
  default     = 20
}

variable "vercel_api_token" {
  description = "Vercel API token used to manage firewall configuration for the leetcode-intelligence client project."
  type        = string
  sensitive   = true
}

variable "vercel_team_id" {
  description = "Vercel team/org ID that owns the leetcode-intelligence client project."
  type        = string
}

variable "vercel_project_id" {
  description = "Vercel project ID for the leetcode-intelligence client."
  type        = string
}

variable "vercel_firewall_enabled" {
  description = "Whether to enable the Vercel Firewall for the leetcode-intelligence client project."
  type        = bool
  default     = true
}

variable "vercel_firewall_ai_bots_enabled" {
  description = "Whether to enable the Vercel managed AI bots ruleset."
  type        = bool
  default     = true
}

variable "vercel_firewall_ai_bots_action" {
  description = "Firewall action for the managed AI bots ruleset."
  type        = string
  default     = "deny"
}

variable "vercel_firewall_bot_protection_enabled" {
  description = "Whether to enable the Vercel managed bot protection ruleset."
  type        = bool
  default     = true
}

variable "vercel_firewall_bot_protection_action" {
  description = "Firewall action for the managed bot protection ruleset."
  type        = string
  default     = "challenge"
}

variable "non_admin_rate_limit_max_requests" {
  description = "Maximum number of requests allowed per IP in one rate-limit window."
  type        = number
  default     = 120
}

variable "non_admin_rate_limit_window_seconds" {
  description = "Rate-limit window length in seconds."
  type        = number
  default     = 60
}
