variable "grafana_url" {
  description = "Base URL of the Grafana instance."
  type        = string
}

variable "grafana_auth" {
  description = "Grafana provider auth string, typically an API token."
  type        = string
  sensitive   = true
}

variable "grafana_folder_title" {
  description = "Grafana folder title for strategy-tester dashboards."
  type        = string
  default     = "Strategy Tester"
}

variable "grafana_folder_uid" {
  description = "Stable Grafana folder UID for strategy-tester dashboards."
  type        = string
  default     = "strategy-tester-folder"
}

variable "strategy_tester_namespace" {
  description = "Kubernetes namespace where strategy-tester services run."
  type        = string
  default     = "strategy-tester"
}

variable "neon_datasource_uid" {
  description = "Grafana datasource UID for the Neon-backed PostgreSQL datasource used by strategy-tester."
  type        = string
}
