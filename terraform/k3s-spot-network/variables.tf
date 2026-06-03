variable "aws_region" {
  description = "AWS region where the spot network resources are created"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Logical name for the target k3s cluster"
  type        = string
  default     = "openhands-k3s"
}

variable "network_name" {
  description = "Name suffix used for the low-cost spot worker network"
  type        = string
  default     = "spot-network"
}

variable "vpc_cidr" {
  description = "CIDR block assigned to the dedicated VPC"
  type        = string
  default     = "10.44.0.0/16"
}

variable "public_subnet_count" {
  description = "How many public subnets to create across distinct availability zones"
  type        = number
  default     = 2

  validation {
    condition     = var.public_subnet_count >= 1 && var.public_subnet_count <= 3
    error_message = "public_subnet_count must be between 1 and 3."
  }
}

variable "tags" {
  description = "Tags applied to all AWS resources in this stack"
  type        = map(string)
  default = {
    project    = "homelab-cloud"
    managed_by = "terraform"
  }
}
