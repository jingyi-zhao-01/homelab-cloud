output "flashsale_dashboard_folder_uid" {
  description = "UID of the Grafana folder containing flashsale dashboards."
  value       = grafana_folder.flashsale.uid
}

output "flashsale_async_terminalization_dashboard_uid" {
  description = "UID of the async terminalization dashboard."
  value       = grafana_dashboard.flashsale_async_terminalization.uid
}

output "flashsale_async_terminalization_dashboard_url" {
  description = "Direct URL for the async terminalization dashboard."
  value       = grafana_dashboard.flashsale_async_terminalization.url
}
