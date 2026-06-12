variable "aws_region" {
  description = "AWS region where control-plane-triage-agent SSM parameters are created."
  type        = string
  default     = "us-west-1"
}

variable "ssm_path_prefix" {
  description = "SSM parameter path prefix. Parameters are created under /<prefix>/KEY."
  type        = string
  default     = "control-plane-triage-agent/prod"
}

variable "kms_key_id" {
  description = "KMS key ID or alias used to encrypt SecureString parameters. Leave empty to use the AWS-managed default key."
  type        = string
  default     = ""
}

variable "ssm_tags" {
  description = "Tags applied to all control-plane-triage-agent SSM parameters."
  type        = map(string)
  default = {
    project    = "control-plane-triage-agent"
    managed_by = "terraform"
  }
}

variable "openrouter_api_key" {
  description = "Optional direct override for the OpenRouter API key. Leave empty to read from SSM."
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_token" {
  description = "Optional direct override for the GitHub token. Leave empty to read from SSM."
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_token_parameter_name" {
  description = "Global SSM parameter name containing the source GitHub token used to seed the control-plane triage agent secret."
  type        = string
  default     = "/codex/GITHUB_ACCESS_TOKEN"
}

variable "discord_bot_token" {
  description = "Optional direct override for the Discord bot token. Leave empty to read from SSM."
  type        = string
  sensitive   = true
  default     = ""
}

variable "discord_bot_token_parameter_name" {
  description = "Global SSM parameter name containing the source Discord bot token used to seed the control-plane triage agent secret."
  type        = string
  default     = "/codex/DISCORD_TOKEN"
}

variable "discord_channel_id" {
  description = "Optional direct override for the Discord channel ID. Leave empty to read from SSM."
  type        = string
  default     = ""
}

variable "discord_channel_id_parameter_name" {
  description = "Global SSM parameter name containing the source Discord channel ID used to seed the control-plane triage agent secret."
  type        = string
  default     = "/codex/DISCORD_CHANNEL_ID"
}

variable "discord_webhook_url" {
  description = "Optional direct override for the Discord webhook URL. Leave empty to read from SSM."
  type        = string
  sensitive   = true
  default     = ""
}

variable "discord_webhook_url_parameter_name" {
  description = "Global SSM parameter name containing the source Discord webhook URL used to seed the control-plane triage agent secret."
  type        = string
  default     = ""
}

variable "openrouter_api_key_parameter_name" {
  description = "Global SSM parameter name containing the source OpenRouter API key used to seed the control-plane triage agent secret."
  type        = string
  default     = "/codex/OPEN_ROUTER_API_KEY"
}
