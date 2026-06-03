variable "aws_region" {
  description = "AWS region where the spot node resources are created"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Logical name for the target k3s cluster"
  type        = string
  default     = "openhands-k3s"
}

variable "node_group_name" {
  description = "Name suffix used for the spot-backed k3s worker group"
  type        = string
  default     = "spot-worker"
}

variable "vpc_id" {
  description = "VPC where the spot instance and security group are created"
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Subnets where the Auto Scaling Group is allowed to place the spot instance"
  type        = list(string)
  default     = []
}

variable "network_state_bucket" {
  description = "Optional S3 bucket that stores the low-cost spot network remote state"
  type        = string
  default     = null
}

variable "network_state_key" {
  description = "S3 key used by the low-cost spot network remote state"
  type        = string
  default     = "k3s/spot-network/terraform.tfstate"
}

variable "key_name" {
  description = "Optional EC2 key pair name for SSH access"
  type        = string
  default     = null
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH to the spot instance. Leave empty to disable SSH ingress."
  type        = list(string)
  default     = []
}

variable "trusted_cluster_cidrs" {
  description = "CIDR blocks allowed to reach the spot worker for k3s node-to-node traffic, pod overlay traffic, and node-level scrapes such as node-exporter. Use the server/VPN/private ranges that must talk to this worker."
  type        = list(string)
  default     = []
}

variable "associate_public_ip_address" {
  description = "Whether the spot instance should receive a public IP on launch"
  type        = bool
  default     = true
}

variable "instance_types" {
  description = "Ordered list of EC2 instance types the ASG may use for the spot worker"
  type        = list(string)
  default     = ["t3.small", "t3a.small"]
}

variable "ami_ssm_parameter" {
  description = "SSM parameter name resolving to the AMI ID used for the spot worker"
  type        = string
  default     = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

variable "k3s_server_url" {
  description = "Reachable URL for the existing k3s server, for example https://<server-ip>:6443"
  type        = string
}

variable "k3s_token" {
  description = "Shared k3s token used by the spot instance to join the existing cluster"
  type        = string
  sensitive   = true
}

variable "tailscale_enabled" {
  description = "Whether the spot worker should install Tailscale during bootstrap and prefer its Tailscale IP for k3s node registration"
  type        = bool
  default     = false
}

variable "tailscale_auth_key" {
  description = "Optional pre-auth Tailscale auth key used by the spot worker to join the tailnet"
  type        = string
  default     = null
  sensitive   = true
}

variable "tailscale_advertise_tags" {
  description = "Optional Tailscale ACL tags to advertise when the spot worker joins the tailnet"
  type        = list(string)
  default     = []
}

variable "tailscale_hostname" {
  description = "Optional hostname override used when the spot worker joins Tailscale"
  type        = string
  default     = null
}

variable "node_labels" {
  description = "Extra labels passed to k3s agent as --node-label"
  type        = list(string)
  default     = ["node-purpose=worker", "capacity-type=spot"]
}

variable "node_taints" {
  description = "Optional taints passed to k3s agent as --node-taint"
  type        = list(string)
  default     = []
}

variable "extra_k3s_agent_args" {
  description = "Additional raw arguments appended to INSTALL_K3S_EXEC for the k3s agent"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to all AWS resources in this stack"
  type        = map(string)
  default = {
    project    = "homelab-cloud"
    managed_by = "terraform"
  }
}
