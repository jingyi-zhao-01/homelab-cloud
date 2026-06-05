output "postgres_user_arn" {
  description = "ARN of the POSTGRES_USER SSM parameter"
  value       = aws_ssm_parameter.postgres_user.arn
}

output "postgres_password_arn" {
  description = "ARN of the POSTGRES_PASSWORD SSM parameter"
  value       = aws_ssm_parameter.postgres_password.arn
}

output "postgres_db_arn" {
  description = "ARN of the POSTGRES_DB SSM parameter"
  value       = aws_ssm_parameter.postgres_db.arn
}

output "database_url_arn" {
  description = "ARN of the DATABASE_URL SSM parameter"
  value       = aws_ssm_parameter.database_url.arn
}

output "grafana_service_account_token_arn" {
  description = "ARN of the grafana-service-account-token SSM parameter"
  value       = aws_ssm_parameter.grafana_service_account_token.arn
}

output "llm_api_key_arn" {
  description = "ARN of the llm-api-key SSM parameter"
  value       = aws_ssm_parameter.llm_api_key.arn
}

output "parameter_path_prefix" {
  description = "SSM path prefix under which all parameters are stored"
  value       = "/${var.ssm_path_prefix}"
}
