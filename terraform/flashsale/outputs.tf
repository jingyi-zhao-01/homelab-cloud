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
  value       = module.grafana_dashboards.flashsale_dashboard_folder_uid
}

output "flashsale_order_service_dashboard_url" {
  description = "Direct URL for the Flashsale Order Service dashboard."
  value       = module.grafana_dashboards.flashsale_order_service_dashboard_url
}

output "flashsale_product_service_dashboard_url" {
  description = "Direct URL for the Flashsale Product Service dashboard."
  value       = module.grafana_dashboards.flashsale_product_service_dashboard_url
}

output "flashsale_terminalization_queue_health_dashboard_url" {
  description = "Direct URL for the Flashsale Terminalization Queue Health dashboard."
  value       = module.grafana_dashboards.flashsale_terminalization_queue_health_dashboard_url
}

output "flashsale_terminalization_outcomes_dashboard_url" {
  description = "Direct URL for the Flashsale Terminalization Outcomes dashboard."
  value       = module.grafana_dashboards.flashsale_terminalization_outcomes_dashboard_url
}

output "flashsale_distributed_traces_dashboard_url" {
  description = "Direct URL for the Flashsale Distributed Traces dashboard."
  value       = module.grafana_dashboards.flashsale_distributed_traces_dashboard_url
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
