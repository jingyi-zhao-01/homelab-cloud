output "openhands_llm_api_key_ssm_parameter_name" {
  description = "SSM parameter name holding the OpenRouter key for the control-plane triage agent."
  value       = aws_ssm_parameter.openhands_llm_api_key.name
}
