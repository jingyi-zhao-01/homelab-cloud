# Flashsale Terraform Stack

This directory is the unified Terraform entrypoint for flashsale infrastructure.

It composes the flashsale-specific pieces that used to live in separate directories:

- Neon PostgreSQL provisioning
- Grafana dashboard provisioning
- Upstash Redis provisioning
- Aiven Kafka provisioning for order terminalization
- AWS SSM Parameter Store secret sync

## Scope

The stack currently manages:

- a Neon project for the shared flashsale PostgreSQL database
- the Grafana folder and dashboards for flashsale observability
- an Upstash Redis database suitable for `order-service` caching, idempotency, or queue-adjacent coordination
- an Aiven Kafka service, terminalization topics, and an order-service Kafka user
- SSM `SecureString` parameters for database, Upstash, and Kafka connection material

## Layout

- `terraform/flashsale/`
  The preferred namespace-level root module for flashsale infrastructure.
- `terraform/neon/`
  Kept for backward compatibility with existing thin-scope applies.
- `terraform/flashsale-grafana-dashboards/`
  Legacy dashboard-only module retained for compatibility, but no longer the preferred workflow entrypoint.

## Why This Exists

Flashsale is no longer just "a Neon database". The workload now has three operational infrastructure surfaces:

- PostgreSQL in Neon
- Grafana dashboards for perf and async-terminalization analysis
- Redis in Upstash
- Kafka in Aiven
- secret distribution in AWS SSM Parameter Store

Putting them behind one Terraform entrypoint makes it easier to reason about flashsale as one deployable platform slice instead of several unrelated stacks.

## Example

```bash
cd terraform/flashsale
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=flashsales/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="encrypt=true"
terraform plan
terraform apply
```

## Required Inputs

- `neon_api_key`
- `grafana_url`
- `grafana_auth`
- `neon_datasource_uid`
- `loki_datasource_uid`
- `tempo_datasource_uid`
- `prometheus_datasource_uid` (optional, defaults to `prometheus`)
- `aws_region`

See [terraform.tfvars.example](./terraform.tfvars.example) for a working starting point.

## Aiven Kafka Provider Bootstrap

By default, this stack reads the Aiven provider API token from AWS SSM Parameter Store:

- `/avien/api_token`
- `/avien/org_id`

Create it manually as a SecureString before running Terraform:

```bash
aws ssm put-parameter \
  --name /avien/api_token \
  --type SecureString \
  --value "YOUR_AIVEN_API_TOKEN" \
  --overwrite

aws ssm put-parameter \
  --name /avien/org_id \
  --type SecureString \
  --value "YOUR_AIVEN_ORG_OR_UNIT_ID" \
  --overwrite
```

The stack creates an Aiven Kafka service with `aiven_kafka_plan = "free-0"` and `aiven_kafka_version = "4.1"` by default, plus:

- an Aiven project named by `aiven_project_name` if it does not already exist in Terraform state
- `flashsale.order.terminalization.v1`
- `flashsale.order.terminalization.retry.v1`
- `flashsale.order.terminalization.dlq.v1`
- a `flashsale-order-service` Kafka user with read/write ACLs on those topics
- a Grafana dashboard for Kafka terminalization health, using the Prometheus datasource configured by `prometheus_datasource_uid`

The default topic shape stays within the Aiven free tier limits: five topics maximum and two partitions maximum per topic.
The current Aiven free tier also requires Kafka `4.1` or newer, which is why the stack defaults to `4.1`.

The Kafka service also enables public Prometheus access so an external Prometheus server can scrape Aiven Kafka metrics. Aiven exposes Kafka metrics such as `kafka_consumer_group_rep_lag`, `kafka_consumer_group_offset`, and broker topic counters like `kafka_server_BrokerTopicMetrics_MessagesInPerSec_Count`.

You can override the SSM lookup or service placement with:

- `aiven_api_token_parameter_name`
- `aiven_org_id_parameter_name`
- `aiven_api_token`
- `aiven_project_name`
- `aiven_project_parent_id`
- `aiven_kafka_cloud_name`
- `aiven_kafka_service_name`

## Upstash Provider Bootstrap

By default, this stack reads the Upstash provider bootstrap credentials from AWS SSM Parameter Store:

- `/upstash/email`
- `/upstash/api_key`

That keeps the provider login separate from project-scoped runtime outputs.

You can still override those values directly with:

- `upstash_email`
- `upstash_api_key`

but the preferred pattern is:

- shared provider bootstrap credentials in `/upstash/*`
- project-scoped runtime outputs under `/flashsales/prod/*`
- a per-database Upstash monthly budget via `upstash_redis_budget` (default `20`)

## Notes

- The Neon and Grafana subdirectories still exist for compatibility, but the preferred automation entrypoint is the namespace-level flashsale stack and its `terraform-flashsale-resources.yml` workflow.
- The Upstash provider stores connection outputs in Terraform state. Treat remote state access as sensitive.
- The stack now mirrors Neon, Upstash, and Kafka credentials into AWS SSM Parameter Store under `/flashsales/prod` by default.
- The SSM path includes `DATABASE_URL`, `POSTGRES_*`, `REDIS_URL`, `UPSTASH_REDIS_*`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SERVICE_URI`, `KAFKA_USERNAME`, `KAFKA_PASSWORD`, `KAFKA_ACCESS_CERT`, `KAFKA_ACCESS_KEY`, and the terminalization topic names.
