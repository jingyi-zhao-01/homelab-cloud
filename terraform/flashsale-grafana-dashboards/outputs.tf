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
