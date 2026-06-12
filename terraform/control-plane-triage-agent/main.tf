terraform {
  required_version = ">= 1.5"

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

data "aws_ssm_parameter" "openrouter_api_key" {
  count           = var.openrouter_api_key == "" ? 1 : 0
  name            = var.openrouter_api_key_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "github_token" {
  count           = var.github_token == "" ? 1 : 0
  name            = var.github_token_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "discord_bot_token" {
  count           = var.discord_bot_token == "" ? 1 : 0
  name            = var.discord_bot_token_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "discord_channel_id" {
  count           = var.discord_channel_id == "" ? 1 : 0
  name            = var.discord_channel_id_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "discord_webhook_url" {
  count           = var.discord_webhook_url == "" && var.discord_webhook_url_parameter_name != "" ? 1 : 0
  name            = var.discord_webhook_url_parameter_name
  with_decryption = true
}

locals {
  ssm_prefix                    = "/${var.ssm_path_prefix}"
  effective_github_token        = var.github_token != "" ? var.github_token : data.aws_ssm_parameter.github_token[0].value
  effective_discord_bot_token   = var.discord_bot_token != "" ? var.discord_bot_token : data.aws_ssm_parameter.discord_bot_token[0].value
  effective_discord_channel_id  = var.discord_channel_id != "" ? var.discord_channel_id : data.aws_ssm_parameter.discord_channel_id[0].value
  effective_discord_webhook_url = var.discord_webhook_url != "" ? var.discord_webhook_url : try(data.aws_ssm_parameter.discord_webhook_url[0].value, "")
  effective_openrouter_key      = var.openrouter_api_key != "" ? var.openrouter_api_key : try(data.aws_ssm_parameter.openrouter_api_key[0].value, "")
}

resource "aws_ssm_parameter" "github_token" {
  name        = "${local.ssm_prefix}/GITHUB_TOKEN"
  description = "GitHub token consumed by the control-plane triage agent for polling workflow runs and fetching logs"
  type        = "SecureString"
  value       = local.effective_github_token
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.ssm_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "discord_webhook_url" {
  count = local.effective_discord_webhook_url != "" ? 1 : 0

  name        = "${local.ssm_prefix}/DISCORD_WEBHOOK_URL"
  description = "Discord webhook URL consumed by the control-plane triage agent for incident notifications"
  type        = "SecureString"
  value       = local.effective_discord_webhook_url
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.ssm_tags
}

resource "aws_ssm_parameter" "discord_bot_token" {
  name        = "${local.ssm_prefix}/DISCORD_BOT_TOKEN"
  description = "Discord bot token consumed by the control-plane triage agent for interactive incident delivery"
  type        = "SecureString"
  value       = local.effective_discord_bot_token
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.ssm_tags
}

resource "aws_ssm_parameter" "discord_channel_id" {
  name        = "${local.ssm_prefix}/DISCORD_CHANNEL_ID"
  description = "Discord channel ID consumed by the control-plane triage agent for bot notifications"
  type        = "String"
  value       = local.effective_discord_channel_id
  overwrite   = true

  tags = var.ssm_tags
}

resource "aws_ssm_parameter" "openhands_llm_api_key" {
  count = local.effective_openrouter_key != "" ? 1 : 0

  name        = "${local.ssm_prefix}/OPENHANDS_LLM_API_KEY"
  description = "OpenRouter API key consumed by the control-plane triage agent via the OpenHands SDK"
  type        = "SecureString"
  value       = local.effective_openrouter_key
  key_id      = var.kms_key_id
  overwrite   = true

  tags = var.ssm_tags
}
