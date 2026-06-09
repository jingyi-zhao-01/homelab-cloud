terraform {
  required_version = ">= 1.5"

  backend "s3" {}

  required_providers {
    grafana = {
      source  = "grafana/grafana"
      version = "~> 4.36"
    }
  }
}

provider "grafana" {
  url  = var.grafana_url
  auth = var.grafana_auth
}

resource "grafana_folder" "strategy_tester" {
  title = var.grafana_folder_title
  uid   = var.grafana_folder_uid
}

locals {
  strategy_tester_volatility_surfaces_dashboard = templatefile(
    "${path.module}/dashboards/strategy-tester-volatility-surfaces.json.tftpl",
    {
      neon_datasource_uid       = var.neon_datasource_uid
      strategy_tester_namespace = var.strategy_tester_namespace
    }
  )
}

resource "grafana_dashboard" "strategy_tester_volatility_surfaces" {
  folder      = grafana_folder.strategy_tester.uid
  overwrite   = true
  config_json = local.strategy_tester_volatility_surfaces_dashboard
}
