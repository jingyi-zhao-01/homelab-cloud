variable "neon_api_key" {
  description = "Neon API key — create one at console.neon.tech → Account Settings → API Keys"
  type        = string
  sensitive   = true
}

variable "neon_region" {
  description = "Neon region id (https://neon.tech/docs/introduction/regions)"
  type        = string
  default     = "aws-us-east-1"
}

variable "neon_history_retention_seconds" {
  description = "Point-in-time restore retention in seconds; 21600 is compatible with the current Neon plan limit"
  type        = number
  default     = 21600
}

variable "kubeconfig_path" {
  description = "Path to kubeconfig used to write the K8s secret"
  type        = string
  default     = "../../secrets/.kube-config"
}

variable "k8s_namespace" {
  description = "Kubernetes namespace where flashsales is deployed"
  type        = string
  default     = "flashsales"
}
