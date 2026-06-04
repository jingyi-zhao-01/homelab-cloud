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
  description = "Grafana folder title for flashsale dashboards."
  type        = string
  default     = "Flashsale"
}

variable "grafana_folder_uid" {
  description = "Stable Grafana folder UID for flashsale dashboards."
  type        = string
  default     = "flashsale-folder"
}

variable "flashsale_namespace" {
  description = "Kubernetes namespace where flashsale services run."
  type        = string
  default     = "flashsales"
}

variable "neon_datasource_uid" {
  description = "Grafana datasource UID for the Neon-backed PostgreSQL datasource used by flashsale."
  type        = string
}

variable "loki_datasource_uid" {
  description = "Grafana datasource UID for the Loki logs datasource."
  type        = string
}

variable "processing_sla_minutes" {
  description = "Minutes after which a processing task is treated as stuck."
  type        = number
  default     = 5
}
