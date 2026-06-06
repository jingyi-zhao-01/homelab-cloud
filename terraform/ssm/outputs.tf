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

output "redis_url_arn" {
  description = "ARN of the REDIS_URL SSM parameter"
  value       = try(aws_ssm_parameter.redis_url[0].arn, null)
}

output "upstash_redis_endpoint_arn" {
  description = "ARN of the UPSTASH_REDIS_ENDPOINT SSM parameter"
  value       = try(aws_ssm_parameter.upstash_redis_endpoint[0].arn, null)
}

output "upstash_redis_port_arn" {
  description = "ARN of the UPSTASH_REDIS_PORT SSM parameter"
  value       = try(aws_ssm_parameter.upstash_redis_port[0].arn, null)
}

output "upstash_redis_password_arn" {
  description = "ARN of the UPSTASH_REDIS_PASSWORD SSM parameter"
  value       = try(aws_ssm_parameter.upstash_redis_password[0].arn, null)
}

output "upstash_redis_rest_token_arn" {
  description = "ARN of the UPSTASH_REDIS_REST_TOKEN SSM parameter"
  value       = try(aws_ssm_parameter.upstash_redis_rest_token[0].arn, null)
}

output "upstash_redis_read_only_rest_token_arn" {
  description = "ARN of the UPSTASH_REDIS_READ_ONLY_REST_TOKEN SSM parameter"
  value       = try(aws_ssm_parameter.upstash_redis_read_only_rest_token[0].arn, null)
}

output "parameter_path_prefix" {
  description = "SSM path prefix under which all parameters are stored"
  value       = "/${var.ssm_path_prefix}"
}
