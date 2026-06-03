terraform {
  required_version = ">= 1.5"

  # Partial configuration — bucket/key/region are passed via -backend-config at init time.
  # Set TF_STATE_BUCKET and AWS credentials in CI secrets/vars.
  backend "s3" {}

  required_providers {
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.6"
    }
  }
}

provider "neon" {
  api_key = var.neon_api_key
}

resource "neon_project" "flashsales" {
  name                      = "flashsales"
  region_id                 = var.neon_region
  history_retention_seconds = var.neon_history_retention_seconds
}

locals {
  database_url = "postgresql://${neon_project.flashsales.database_user}:${neon_project.flashsales.database_password}@${neon_project.flashsales.database_host}/${neon_project.flashsales.database_name}?sslmode=require"
}
