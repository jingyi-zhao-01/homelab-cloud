output "flashsale_dashboard_folder_uid" {
  description = "UID of the Grafana folder containing flashsale dashboards."
  value       = grafana_folder.flashsale.uid
}

output "flashsale_http_throughput_dashboard_url" {
  description = "Direct URL for the Flashsale HTTP Throughput dashboard."
  value       = grafana_dashboard.flashsale_http_throughput.url
}

output "flashsale_http_latency_dashboard_url" {
  description = "Direct URL for the Flashsale HTTP Latency dashboard."
  value       = grafana_dashboard.flashsale_http_latency.url
}

output "flashsale_terminalization_queue_health_dashboard_url" {
  description = "Direct URL for the Flashsale Terminalization Queue Health dashboard."
  value       = grafana_dashboard.flashsale_terminalization_queue_health.url
}

output "flashsale_terminalization_outcomes_dashboard_url" {
  description = "Direct URL for the Flashsale Terminalization Outcomes dashboard."
  value       = grafana_dashboard.flashsale_terminalization_outcomes.url
}
