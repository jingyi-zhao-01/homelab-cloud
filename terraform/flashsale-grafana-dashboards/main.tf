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

resource "grafana_folder" "flashsale" {
  title = var.grafana_folder_title
  uid   = var.grafana_folder_uid
}

locals {
  flashsale_async_terminalization_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-async-terminalization.json.tftpl",
    {
      neon_datasource_uid    = var.neon_datasource_uid
      loki_datasource_uid    = var.loki_datasource_uid
      namespace              = var.flashsale_namespace
      processing_sla_minutes = var.processing_sla_minutes
    }
  )
}

resource "grafana_dashboard" "flashsale_async_terminalization" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_async_terminalization_dashboard
}
