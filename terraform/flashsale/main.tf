terraform {
  required_version = ">= 1.5"

  # Partial configuration — bucket/key/region are passed via -backend-config at init time.
  # Set TF_STATE_BUCKET and AWS credentials in CI secrets/vars.
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }

    upstash = {
      source  = "upstash/upstash"
      version = "~> 2.1"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_ssm_parameter" "upstash_email" {
  count = var.upstash_email == "" ? 1 : 0
  name  = var.upstash_email_parameter_name
}

data "aws_ssm_parameter" "upstash_api_key" {
  count           = var.upstash_api_key == "" ? 1 : 0
  name            = var.upstash_api_key_parameter_name
  with_decryption = true
}

locals {
  upstash_provider_email   = var.upstash_email != "" ? var.upstash_email : nonsensitive(data.aws_ssm_parameter.upstash_email[0].value)
  upstash_provider_api_key = var.upstash_api_key != "" ? var.upstash_api_key : data.aws_ssm_parameter.upstash_api_key[0].value
}

provider "upstash" {
  email   = local.upstash_provider_email
  api_key = local.upstash_provider_api_key
}

module "neon" {
  source = "../neon"

  neon_api_key                   = var.neon_api_key
  neon_region                    = var.neon_region
  neon_history_retention_seconds = var.neon_history_retention_seconds
}

resource "grafana_folder" "flashsale" {
  title = var.grafana_folder_title
  uid   = var.grafana_folder_uid
}

locals {
  order_service_dashboard_json = templatefile("/dashboards/flashsale-order-service.json.tftpl", {
    datasource_uid      = var.neon_datasource_uid
    loki_datasource_uid = var.loki_datasource_uid
    namespace           = var.flashsale_namespace
  })

  product_service_dashboard_json = templatefile("/dashboards/flashsale-product-service.json.tftpl", {
    datasource_uid      = var.neon_datasource_uid
    loki_datasource_uid = var.loki_datasource_uid
    namespace           = var.flashsale_namespace
  })

  queue_health_dashboard_json = templatefile("/dashboards/flashsale-terminalization-queue-health.json.tftpl", {
    datasource_uid        = var.neon_datasource_uid
    loki_datasource_uid   = var.loki_datasource_uid
    namespace             = var.flashsale_namespace
    processing_sla_minutes = var.processing_sla_minutes
  })

  terminalization_outcomes_dashboard_json = templatefile("/dashboards/flashsale-terminalization-outcomes.json.tftpl", {
    datasource_uid = var.neon_datasource_uid
    namespace      = var.flashsale_namespace
  })

  distributed_traces_dashboard_json = templatefile("/dashboards/flashsale-distributed-traces.json.tftpl", {
    loki_datasource_uid  = var.loki_datasource_uid
    tempo_datasource_uid = var.tempo_datasource_uid
    namespace            = var.flashsale_namespace
  })
}

resource "grafana_dashboard" "flashsale_order_service" {
  folder      = grafana_folder.flashsale.id
  config_json = local.order_service_dashboard_json
}

resource "grafana_dashboard" "flashsale_product_service" {
  folder      = grafana_folder.flashsale.id
  config_json = local.product_service_dashboard_json
}

resource "grafana_dashboard" "flashsale_terminalization_queue_health" {
  folder      = grafana_folder.flashsale.id
  config_json = local.queue_health_dashboard_json
}

resource "grafana_dashboard" "flashsale_terminalization_outcomes" {
  folder      = grafana_folder.flashsale.id
  config_json = local.terminalization_outcomes_dashboard_json
}

resource "grafana_dashboard" "flashsale_distributed_traces" {
  folder      = grafana_folder.flashsale.id
  config_json = local.distributed_traces_dashboard_json
}

resource "upstash_redis_database" "flashsale" {
  database_name  = var.upstash_redis_database_name
  region         = var.upstash_redis_region
  tls            = var.upstash_redis_tls
  eviction       = var.upstash_redis_eviction
  auto_scale     = var.upstash_redis_auto_scale
  primary_region = var.upstash_redis_region == "global" ? var.upstash_redis_primary_region : null
  read_regions   = var.upstash_redis_region == "global" ? var.upstash_redis_read_regions : null
}

locals {
  upstash_redis_scheme = var.upstash_redis_tls ? "rediss" : "redis"
  upstash_redis_url    = "${local.upstash_redis_scheme}://:${upstash_redis_database.flashsale.password}@${upstash_redis_database.flashsale.endpoint}:${upstash_redis_database.flashsale.port}/0"
}

module "ssm" {
  source = "../ssm"

  include_upstash_runtime            = true
  aws_region                         = var.aws_region
  ssm_path_prefix                    = var.ssm_path_prefix
  kms_key_id                         = var.kms_key_id
  postgres_user                      = module.neon.database_user
  postgres_password                  = module.neon.database_password
  postgres_db                        = module.neon.database_name
  database_url                       = module.neon.database_url
  redis_url                          = local.upstash_redis_url
  upstash_redis_endpoint             = upstash_redis_database.flashsale.endpoint
  upstash_redis_port                 = tostring(upstash_redis_database.flashsale.port)
  upstash_redis_password             = upstash_redis_database.flashsale.password
  upstash_redis_rest_token           = upstash_redis_database.flashsale.rest_token
  upstash_redis_read_only_rest_token = upstash_redis_database.flashsale.read_only_rest_token
  tags                               = var.ssm_tags
}
