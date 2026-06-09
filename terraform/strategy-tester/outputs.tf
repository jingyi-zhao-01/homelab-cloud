output "strategy_tester_dashboard_folder_uid" {
  description = "UID of the Grafana folder containing strategy-tester dashboards."
  value       = grafana_folder.strategy_tester.uid
}

output "strategy_tester_volatility_surfaces_dashboard_url" {
  description = "Direct URL for the Strategy Tester Volatility Surfaces dashboard."
  value       = grafana_dashboard.strategy_tester_volatility_surfaces.url
}
