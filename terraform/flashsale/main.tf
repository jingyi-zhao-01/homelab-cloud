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

    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.0"
    }

    grafana = {
      source  = "grafana/grafana"
      version = "~> 4.36"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "grafana" {
  url  = var.grafana_url
  auth = var.grafana_auth
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

data "aws_ssm_parameter" "aiven_api_token" {
  count           = var.aiven_api_token == "" ? 1 : 0
  name            = var.aiven_api_token_parameter_name
  with_decryption = true
}

data "aws_ssm_parameter" "aiven_org_id" {
  count           = var.aiven_project_parent_id == "" ? 1 : 0
  name            = var.aiven_org_id_parameter_name
  with_decryption = true
}

locals {
  upstash_provider_email   = var.upstash_email != "" ? var.upstash_email : nonsensitive(data.aws_ssm_parameter.upstash_email[0].value)
  upstash_provider_api_key = var.upstash_api_key != "" ? var.upstash_api_key : data.aws_ssm_parameter.upstash_api_key[0].value
  aiven_provider_api_token = var.aiven_api_token != "" ? var.aiven_api_token : data.aws_ssm_parameter.aiven_api_token[0].value
  aiven_project_parent_id  = var.aiven_project_parent_id != "" ? var.aiven_project_parent_id : data.aws_ssm_parameter.aiven_org_id[0].value
}

provider "upstash" {
  email   = local.upstash_provider_email
  api_key = local.upstash_provider_api_key
}

provider "aiven" {
  api_token = local.aiven_provider_api_token
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
  order_service_dashboard_json = templatefile("${path.module}/dashboards/flashsale-order-service.json.tftpl", {
    datasource_uid      = var.neon_datasource_uid
    loki_datasource_uid = var.loki_datasource_uid
    namespace           = var.flashsale_namespace
  })

  product_service_dashboard_json = templatefile("${path.module}/dashboards/flashsale-product-service.json.tftpl", {
    datasource_uid      = var.neon_datasource_uid
    loki_datasource_uid = var.loki_datasource_uid
    namespace           = var.flashsale_namespace
  })

  queue_health_dashboard_json = templatefile("${path.module}/dashboards/flashsale-terminalization-queue-health.json.tftpl", {
    neon_datasource_uid    = var.neon_datasource_uid
    loki_datasource_uid    = var.loki_datasource_uid
    namespace              = var.flashsale_namespace
    processing_sla_minutes = var.processing_sla_minutes
  })

  terminalization_outcomes_dashboard_json = templatefile("${path.module}/dashboards/flashsale-terminalization-outcomes.json.tftpl", {
    neon_datasource_uid = var.neon_datasource_uid
    loki_datasource_uid = var.loki_datasource_uid
    namespace           = var.flashsale_namespace
  })

  distributed_traces_dashboard_json = templatefile("${path.module}/dashboards/flashsale-distributed-traces.json.tftpl", {
    loki_datasource_uid  = var.loki_datasource_uid
    tempo_datasource_uid = var.tempo_datasource_uid
    namespace            = var.flashsale_namespace
  })

  kafka_terminalization_dashboard_json = templatefile("${path.module}/dashboards/flashsale-kafka-terminalization.json.tftpl", {
    prometheus_datasource_uid = var.prometheus_datasource_uid
    kafka_service_name        = var.aiven_kafka_service_name
    consumer_group            = var.kafka_terminalization_consumer_group
    terminalization_topic     = var.kafka_terminalization_topic
    retry_topic               = var.kafka_terminalization_retry_topic
    dlq_topic                 = var.kafka_terminalization_dlq_topic
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

resource "grafana_dashboard" "flashsale_kafka_terminalization" {
  folder      = grafana_folder.flashsale.id
  config_json = local.kafka_terminalization_dashboard_json
}

resource "upstash_redis_database" "flashsale" {
  database_name  = var.upstash_redis_database_name
  region         = var.upstash_redis_region
  tls            = var.upstash_redis_tls
  eviction       = var.upstash_redis_eviction
  auto_scale     = var.upstash_redis_auto_scale
  budget         = var.upstash_redis_budget
  primary_region = var.upstash_redis_region == "global" ? var.upstash_redis_primary_region : null
  read_regions   = var.upstash_redis_region == "global" ? var.upstash_redis_read_regions : null
}

locals {
  upstash_redis_scheme = var.upstash_redis_tls ? "rediss" : "redis"
  upstash_redis_url    = "${local.upstash_redis_scheme}://:${upstash_redis_database.flashsale.password}@${upstash_redis_database.flashsale.endpoint}:${upstash_redis_database.flashsale.port}/0"
  aiven_kafka_topic_replication = var.aiven_kafka_plan == "free-0" ? 2 : var.aiven_kafka_topic_replication
}

resource "aiven_project" "flashsale" {
  project       = var.aiven_project_name
  parent_id     = local.aiven_project_parent_id

  tag {
    key   = "project"
    value = "flashsales"
  }

  tag {
    key   = "managed_by"
    value = "terraform"
  }
}

resource "aiven_kafka" "flashsale" {
  project                = aiven_project.flashsale.project
  service_name           = var.aiven_kafka_service_name
  plan                   = var.aiven_kafka_plan
  cloud_name             = var.aiven_kafka_cloud_name == "" ? null : var.aiven_kafka_cloud_name
  termination_protection = var.aiven_kafka_termination_protection

  kafka_user_config {
    kafka_version   = var.aiven_kafka_version
    kafka_rest      = false
    schema_registry = false

    kafka_authentication_methods {
      certificate = true
      sasl        = true
    }

    kafka {
      auto_create_topics_enable        = false
      group_initial_rebalance_delay_ms = 0
      num_partitions                   = var.aiven_kafka_topic_partitions
      default_replication_factor       = local.aiven_kafka_topic_replication
    }

    public_access {
      kafka      = true
      prometheus = true
    }
  }

  tag {
    key   = "project"
    value = "flashsales"
  }

  tag {
    key   = "managed_by"
    value = "terraform"
  }
}

resource "aiven_kafka_user" "order_service" {
  project      = aiven_project.flashsale.project
  service_name = aiven_kafka.flashsale.service_name
  username     = var.aiven_kafka_order_service_username
}

resource "aiven_kafka_topic" "terminalization" {
  project                = aiven_project.flashsale.project
  service_name           = aiven_kafka.flashsale.service_name
  topic_name             = var.kafka_terminalization_topic
  partitions             = var.aiven_kafka_topic_partitions
  replication            = local.aiven_kafka_topic_replication
  termination_protection = var.aiven_kafka_topic_termination_protection
  topic_description      = "Primary flashsale order terminalization command topic."

  config {
    cleanup_policy = "delete"
    retention_ms   = tostring(var.aiven_kafka_terminalization_retention_ms)
  }
}

resource "aiven_kafka_topic" "terminalization_retry" {
  project                = aiven_project.flashsale.project
  service_name           = aiven_kafka.flashsale.service_name
  topic_name             = var.kafka_terminalization_retry_topic
  partitions             = var.aiven_kafka_topic_partitions
  replication            = local.aiven_kafka_topic_replication
  termination_protection = var.aiven_kafka_topic_termination_protection
  topic_description      = "Retry flashsale order terminalization command topic."

  config {
    cleanup_policy = "delete"
    retention_ms   = tostring(var.aiven_kafka_terminalization_retry_retention_ms)
  }
}

resource "aiven_kafka_topic" "terminalization_dlq" {
  project                = aiven_project.flashsale.project
  service_name           = aiven_kafka.flashsale.service_name
  topic_name             = var.kafka_terminalization_dlq_topic
  partitions             = var.aiven_kafka_topic_partitions
  replication            = local.aiven_kafka_topic_replication
  termination_protection = var.aiven_kafka_topic_termination_protection
  topic_description      = "Dead-letter flashsale order terminalization command topic."

  config {
    cleanup_policy = "delete"
    retention_ms   = tostring(var.aiven_kafka_terminalization_dlq_retention_ms)
  }
}

resource "aiven_kafka_acl" "order_service_terminalization" {
  for_each = toset([
    aiven_kafka_topic.terminalization.topic_name,
    aiven_kafka_topic.terminalization_retry.topic_name,
    aiven_kafka_topic.terminalization_dlq.topic_name,
  ])

  project      = aiven_project.flashsale.project
  service_name = aiven_kafka.flashsale.service_name
  topic        = each.value
  permission   = "readwrite"
  username     = aiven_kafka_user.order_service.username
}

locals {
  aiven_kafka_bootstrap_servers = "${aiven_kafka.flashsale.service_host}:${aiven_kafka.flashsale.service_port}"
}

module "ssm" {
  source = "../ssm"

  include_upstash_runtime              = true
  include_aiven_kafka_runtime          = true
  aws_region                           = var.aws_region
  ssm_path_prefix                      = var.ssm_path_prefix
  kms_key_id                           = var.kms_key_id
  postgres_user                        = module.neon.database_user
  postgres_password                    = module.neon.database_password
  postgres_db                          = module.neon.database_name
  database_url                         = module.neon.database_url
  redis_url                            = local.upstash_redis_url
  upstash_redis_endpoint               = upstash_redis_database.flashsale.endpoint
  upstash_redis_port                   = tostring(upstash_redis_database.flashsale.port)
  upstash_redis_password               = upstash_redis_database.flashsale.password
  upstash_redis_rest_token             = upstash_redis_database.flashsale.rest_token
  upstash_redis_read_only_rest_token   = upstash_redis_database.flashsale.read_only_rest_token
  kafka_bootstrap_servers              = local.aiven_kafka_bootstrap_servers
  kafka_service_uri                    = aiven_kafka.flashsale.service_uri
  kafka_security_protocol              = "SSL"
  kafka_username                       = aiven_kafka_user.order_service.username
  kafka_password                       = aiven_kafka_user.order_service.password
  kafka_access_cert                    = aiven_kafka_user.order_service.access_cert
  kafka_access_key                     = aiven_kafka_user.order_service.access_key
  kafka_terminalization_topic          = aiven_kafka_topic.terminalization.topic_name
  kafka_terminalization_retry_topic    = aiven_kafka_topic.terminalization_retry.topic_name
  kafka_terminalization_dlq_topic      = aiven_kafka_topic.terminalization_dlq.topic_name
  kafka_terminalization_consumer_group = var.kafka_terminalization_consumer_group
  tags                                 = var.ssm_tags
}
