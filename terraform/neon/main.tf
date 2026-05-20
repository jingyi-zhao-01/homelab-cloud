terraform {
  required_version = ">= 1.5"

  required_providers {
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.6"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.36"
    }
  }
}

provider "neon" {
  api_key = var.neon_api_key
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

resource "neon_project" "flashsales" {
  name      = "flashsales"
  region_id = var.neon_region

  default_branch_database_name = "flashsales"
  default_branch_role_name     = "flashsales"
}

locals {
  database_url = "postgresql://${neon_project.flashsales.database_user}:${neon_project.flashsales.database_password}@${neon_project.flashsales.database_host}/flashsales?sslmode=require"
}

# Writes the Neon credentials into the same Secret name the Helm chart expects,
# so no changes are needed to how deployments pull DB_USER / DB_PASSWORD.
# DATABASE_URL is added as a new key; services pick it up automatically because
# config.py checks DATABASE_URL first.
resource "kubernetes_secret_v1" "neon_credentials" {
  metadata {
    name      = "flashsales-postgres-auth"
    namespace = var.k8s_namespace
  }

  data = {
    POSTGRES_USER     = neon_project.flashsales.database_user
    POSTGRES_PASSWORD = neon_project.flashsales.database_password
    POSTGRES_DB       = neon_project.flashsales.database_name
    DATABASE_URL      = local.database_url
  }
}
