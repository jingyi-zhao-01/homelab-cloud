
variable "namespace" {
  type    = string
  default = "default"
}

variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "kubeconfig_context" {
  type     = string
  default  = null
  nullable = true
}

variable "cluster_name" {
  type    = string
  default = "openhands-k3s"
}

variable "destinations_loki_url" {
  type    = string
  default = "https://logs-prod-021.grafana.net/loki/api/v1/push"
}

variable "destinations_loki_username" {
  type    = string
  default = "1284914"
}

variable "destinations_loki_password" {
  type      = string
  sensitive = true
}

variable "fleetmanagement_url" {
  type    = string
  default = "https://fleet-management-prod-014.grafana.net"
}

variable "fleetmanagement_username" {
  type    = string
  default = "1327120"
}

variable "fleetmanagement_password" {
  type      = string
  sensitive = true
}
