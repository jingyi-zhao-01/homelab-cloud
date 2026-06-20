output "project_id" {
  description = "Neon project ID."
  value       = module.neon.project_id
}

output "database_host" {
  description = "Neon database hostname."
  value       = module.neon.database_host
}

output "database_url" {
  description = "Full Neon DATABASE_URL connection string."
  value       = module.neon.database_url
  sensitive   = true
}

output "database_user" {
  description = "Neon database username."
  value       = module.neon.database_user
  sensitive   = true
}

output "database_password" {
  description = "Neon database password."
  value       = module.neon.database_password
  sensitive   = true
}

output "database_name" {
  description = "Neon database name."
  value       = module.neon.database_name
  sensitive   = true
}

output "flashsale_dashboard_folder_uid" {
  description = "UID of the Grafana folder containing flashsale dashboards."
  value       = grafana_folder.flashsale.uid
}

output "flashsale_order_service_dashboard_url" {
  description = "Direct URL for the Flashsale Order Service dashboard."
  value       = grafana_dashboard.flashsale_order_service.url
}

output "flashsale_product_service_dashboard_url" {
  description = "Direct URL for the Flashsale Product Service dashboard."
  value       = grafana_dashboard.flashsale_product_service.url
}

output "flashsale_terminalization_queue_health_dashboard_url" {
  description = "Direct URL for the Flashsale Terminalization Queue Health dashboard."
  value       = grafana_dashboard.flashsale_terminalization_queue_health.url
}

output "flashsale_terminalization_outcomes_dashboard_url" {
  description = "Direct URL for the Flashsale Terminalization Outcomes dashboard."
  value       = grafana_dashboard.flashsale_terminalization_outcomes.url
}

output "flashsale_distributed_traces_dashboard_url" {
  description = "Direct URL for the Flashsale Distributed Traces dashboard."
  value       = grafana_dashboard.flashsale_distributed_traces.url
}

output "flashsale_kafka_terminalization_dashboard_url" {
  description = "Direct URL for the Flashsale Kafka Terminalization dashboard."
  value       = grafana_dashboard.flashsale_kafka_terminalization.url
}

output "upstash_redis_database_id" {
  description = "Upstash Redis database ID."
  value       = upstash_redis_database.flashsale.database_id
}

output "upstash_redis_endpoint" {
  description = "Upstash Redis endpoint hostname."
  value       = upstash_redis_database.flashsale.endpoint
}

output "upstash_redis_port" {
  description = "Upstash Redis port."
  value       = upstash_redis_database.flashsale.port
}

output "upstash_redis_password" {
  description = "Upstash Redis password."
  value       = upstash_redis_database.flashsale.password
  sensitive   = true
}

output "upstash_redis_rest_token" {
  description = "Upstash Redis REST token."
  value       = upstash_redis_database.flashsale.rest_token
  sensitive   = true
}

output "upstash_redis_read_only_rest_token" {
  description = "Upstash Redis read-only REST token."
  value       = upstash_redis_database.flashsale.read_only_rest_token
  sensitive   = true
}

output "upstash_redis_url" {
  description = "Redis URL for flashsale order-service style clients."
  value       = local.upstash_redis_url
  sensitive   = true
}

output "ssm_parameter_path_prefix" {
  description = "SSM path prefix under which flashsale secrets are stored."
  value       = module.ssm.parameter_path_prefix
}

output "aiven_kafka_service_name" {
  description = "Aiven Kafka service name for flashsale terminalization."
  value       = aiven_kafka.flashsale.service_name
}

output "aiven_kafka_bootstrap_servers" {
  description = "Kafka bootstrap servers for flashsale workloads."
  value       = local.aiven_kafka_bootstrap_servers
}

output "aiven_kafka_service_uri" {
  description = "Aiven Kafka service URI."
  value       = aiven_kafka.flashsale.service_uri
  sensitive   = true
}

output "aiven_kafka_order_service_username" {
  description = "Kafka username for flashsale order-service and order-worker."
  value       = var.aiven_kafka_order_service_username
}

output "kafka_terminalization_topic" {
  description = "Primary flashsale order terminalization Kafka topic."
  value       = aiven_kafka_topic.terminalization.topic_name
}

output "kafka_terminalization_retry_topic" {
  description = "Retry flashsale order terminalization Kafka topic."
  value       = aiven_kafka_topic.terminalization_retry.topic_name
}

output "kafka_terminalization_dlq_topic" {
  description = "Dead-letter flashsale order terminalization Kafka topic."
  value       = aiven_kafka_topic.terminalization_dlq.topic_name
}

output "kafka_terminalization_consumer_group" {
  description = "Kafka consumer group used by the flashsale terminalization worker."
  value       = var.kafka_terminalization_consumer_group
}
