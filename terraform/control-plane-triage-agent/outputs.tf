output "github_token_ssm_parameter_name" {
  description = "SSM parameter name holding the GitHub token for the control-plane triage agent."
  value       = aws_ssm_parameter.github_token.name
}

output "discord_webhook_url_ssm_parameter_name" {
  description = "SSM parameter name holding the Discord webhook URL for the control-plane triage agent."
  value       = try(aws_ssm_parameter.discord_webhook_url[0].name, null)
}

output "discord_bot_token_ssm_parameter_name" {
  description = "SSM parameter name holding the Discord bot token for the control-plane triage agent."
  value       = aws_ssm_parameter.discord_bot_token.name
}

output "discord_channel_id_ssm_parameter_name" {
  description = "SSM parameter name holding the Discord channel ID for the control-plane triage agent."
  value       = aws_ssm_parameter.discord_channel_id.name
}

output "openhands_llm_api_key_ssm_parameter_name" {
  description = "SSM parameter name holding the OpenRouter key for the control-plane triage agent."
  value       = try(aws_ssm_parameter.openhands_llm_api_key[0].name, null)
}
