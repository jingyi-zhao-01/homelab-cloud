# Flashsale Grafana Dashboards

This Terraform module provisions Grafana dashboards for the flashsale workload.

## Scope

Current dashboard set:

- `Flashsale Async Terminalization`

This dashboard exists to support [ADR 0002](../../flashsale/docs/adrs/0002-async-reservation-terminalization.md), which moves reservation `confirm/cancel` off the synchronous order path and requires queue-health style visibility.

## Datasource Model

The SQL panels in this module use a Grafana `PostgreSQL` datasource whose backing database is Neon.

That is why the Terraform variable is named:

- `neon_datasource_uid`

It is still a PostgreSQL datasource from Grafana's point of view. The distinction here is operational:

- Grafana datasource type: `PostgreSQL`
- Actual database provider behind it: `Neon`

The log panels use:

- `loki_datasource_uid`

## Required Inputs

- `grafana_url`
- `grafana_auth`
- `neon_datasource_uid`
- `loki_datasource_uid`

Optional but commonly used:

- `flashsale_namespace`
- `processing_sla_minutes`

## Example

```tf
grafana_url           = "https://grafana.example.com"
grafana_auth          = "YOUR_GRAFANA_API_TOKEN"
neon_datasource_uid   = "flashsale-neon"
loki_datasource_uid   = "loki"
flashsale_namespace   = "flashsales"
processing_sla_minutes = 5
```

## What The Dashboard Shows

The current dashboard focuses on the async terminalization path introduced by ADR 0002:

- terminalization backlog
- oldest queued age
- retry count by action
- stuck processing tasks
- orders still waiting on reservation work
- terminalization success / retry / error log trends
- terminalization worker logs

## Validation

The module is expected to pass:

```bash
terraform init -backend=false
terraform validate
```

## GitHub Actions Automation

This module is automatically applied by:

- [terraform-flashsale-grafana-dashboards.yml](../../.github/workflows/terraform-flashsale-grafana-dashboards.yml)

Automation behavior:

- push to `main` with changes under `terraform/flashsale-grafana-dashboards/**` triggers an automatic `terraform apply`
- manual `workflow_dispatch` supports `plan`, `apply`, and `destroy`

Required GitHub configuration:

Secrets:

- `GRAFANA_AUTH`
- `TF_STATE_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Variables:

- `AWS_REGION`
- `GRAFANA_URL`
- `FLASHSALE_GRAFANA_NEON_DATASOURCE_UID`
- `FLASHSALE_GRAFANA_LOKI_DATASOURCE_UID`

Optional variables:

- `FLASHSALE_NAMESPACE`
- `FLASHSALE_GRAFANA_PROCESSING_SLA_MINUTES`
- `FLASHSALE_GRAFANA_FOLDER_TITLE`
- `FLASHSALE_GRAFANA_FOLDER_UID`
