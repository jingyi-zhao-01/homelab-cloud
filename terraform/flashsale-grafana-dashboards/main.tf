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
  flashsale_order_service_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-order-service.json.tftpl",
    {
      loki_datasource_uid = var.loki_datasource_uid
      namespace           = var.flashsale_namespace
    }
  )

  flashsale_product_service_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-product-service.json.tftpl",
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

  flashsale_distributed_traces_dashboard = templatefile(
    "${path.module}/dashboards/flashsale-distributed-traces.json.tftpl",
    {
      tempo_datasource_uid = var.tempo_datasource_uid
      namespace            = var.flashsale_namespace
    }
  )
}

resource "grafana_dashboard" "flashsale_order_service" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_order_service_dashboard
}

resource "grafana_dashboard" "flashsale_product_service" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_product_service_dashboard
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

resource "grafana_dashboard" "flashsale_distributed_traces" {
  folder      = grafana_folder.flashsale.uid
  overwrite   = true
  config_json = local.flashsale_distributed_traces_dashboard
}
