output "upstash_redis_database_id" {
  description = "Upstash Redis database ID."
  value       = upstash_redis_database.leetcode_intelligence.database_id
}

output "upstash_redis_endpoint" {
  description = "Upstash Redis endpoint hostname."
  value       = upstash_redis_database.leetcode_intelligence.endpoint
}

output "upstash_redis_rest_url_ssm_parameter_name" {
  description = "SSM parameter name holding the Upstash REST URL."
  value       = aws_ssm_parameter.upstash_redis_rest_url.name
}

output "upstash_redis_rest_token_ssm_parameter_name" {
  description = "SSM parameter name holding the Upstash REST token."
  value       = aws_ssm_parameter.upstash_redis_rest_token.name
}
