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

output "kafka_bootstrap_servers_arn" {
  description = "ARN of the KAFKA_BOOTSTRAP_SERVERS SSM parameter"
  value       = try(aws_ssm_parameter.kafka_bootstrap_servers[0].arn, null)
}

output "kafka_service_uri_arn" {
  description = "ARN of the KAFKA_SERVICE_URI SSM parameter"
  value       = try(aws_ssm_parameter.kafka_service_uri[0].arn, null)
}

output "kafka_security_protocol_arn" {
  description = "ARN of the KAFKA_SECURITY_PROTOCOL SSM parameter"
  value       = try(aws_ssm_parameter.kafka_security_protocol[0].arn, null)
}

output "kafka_username_arn" {
  description = "ARN of the KAFKA_USERNAME SSM parameter"
  value       = try(aws_ssm_parameter.kafka_username[0].arn, null)
}

output "kafka_password_arn" {
  description = "ARN of the KAFKA_PASSWORD SSM parameter"
  value       = try(aws_ssm_parameter.kafka_password[0].arn, null)
}

output "kafka_access_cert_arn" {
  description = "ARN of the KAFKA_ACCESS_CERT SSM parameter"
  value       = try(aws_ssm_parameter.kafka_access_cert[0].arn, null)
}

output "kafka_access_key_arn" {
  description = "ARN of the KAFKA_ACCESS_KEY SSM parameter"
  value       = try(aws_ssm_parameter.kafka_access_key[0].arn, null)
}

output "kafka_terminalization_topic_arn" {
  description = "ARN of the KAFKA_TERMINALIZATION_TOPIC SSM parameter"
  value       = try(aws_ssm_parameter.kafka_terminalization_topic[0].arn, null)
}

output "kafka_terminalization_retry_topic_arn" {
  description = "ARN of the KAFKA_TERMINALIZATION_RETRY_TOPIC SSM parameter"
  value       = try(aws_ssm_parameter.kafka_terminalization_retry_topic[0].arn, null)
}

output "kafka_terminalization_dlq_topic_arn" {
  description = "ARN of the KAFKA_TERMINALIZATION_DLQ_TOPIC SSM parameter"
  value       = try(aws_ssm_parameter.kafka_terminalization_dlq_topic[0].arn, null)
}

output "kafka_terminalization_consumer_group_arn" {
  description = "ARN of the KAFKA_TERMINALIZATION_CONSUMER_GROUP SSM parameter"
  value       = try(aws_ssm_parameter.kafka_terminalization_consumer_group[0].arn, null)
}

output "parameter_path_prefix" {
  description = "SSM path prefix under which all parameters are stored"
  value       = "/${var.ssm_path_prefix}"
}
