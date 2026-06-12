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

locals {
  ssm_prefix               = "/${var.ssm_path_prefix}"
  effective_openrouter_key = var.openrouter_api_key != "" ? var.openrouter_api_key : try(data.aws_ssm_parameter.openrouter_api_key[0].value, "")
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
