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
  flashsale_http_throughput_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-http-throughput.json.tftpl",
    {
      loki_datasource_uid = var.loki_datasource_uid
      namespace           = var.flashsale_namespace
    }
  )

  flashsale_http_latency_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-http-latency.json.tftpl",
    {
      loki_datasource_uid = var.loki_datasource_uid
      namespace           = var.flashsale_namespace
    }
  )

  flashsale_terminalization_queue_health_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-terminalization-queue-health.json.tftpl",
    {
      neon_datasource_uid = var.neon_datasource_uid
      namespace           = var.flashsale_namespace
    }
  )

  flashsale_terminalization_outcomes_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-terminalization-outcomes.json.tftpl",
    {
      neon_datasource_uid = var.neon_datasource_uid
      loki_datasource_uid = var.loki_datasource_uid
      namespace           = var.flashsale_namespace
    }
  )
}

resource "grafana_dashboard" "flashsale_http_throughput" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_http_throughput_dashboard
}

resource "grafana_dashboard" "flashsale_http_latency" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_http_latency_dashboard
}

resource "grafana_dashboard" "flashsale_terminalization_queue_health" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_terminalization_queue_health_dashboard
}

resource "grafana_dashboard" "flashsale_terminalization_outcomes" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_terminalization_outcomes_dashboard
}
