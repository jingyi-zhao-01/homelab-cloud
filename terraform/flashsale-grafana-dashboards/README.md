# Flashsale Grafana Dashboards

This Terraform module provisions Grafana dashboards for the flashsale workload.

## Scope

Current dashboard set:

- `Flashsale HTTP Throughput`
- `Flashsale HTTP Latency`
- `Flashsale Terminalization Queue Health`
- `Flashsale Terminalization Outcomes`

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

## What The Dashboards Show

This module now provisions only four dashboards, and every panel is time-based (`timeseries`).

1. `Flashsale HTTP Throughput`

- purpose: show whether perf traffic is actually entering the system and which endpoint is the hotspot
- read it like this: first confirm `POST /orders` rises with the load test, then compare total throughput with error throughput to see whether the system is degrading or merely busy

2. `Flashsale HTTP Latency`

- purpose: show baseline latency and tail-latency regression by endpoint
- read it like this: start with `p50`, then `p95`, then `p99`; if only tail latency rises, the system is entering contention before full collapse

3. `Flashsale Terminalization Queue Health`

- purpose: show whether the async queue is absorbing pressure or accumulating debt
- read it like this: compare enqueue rate against worker claim rate; if backlog climbs while claim rate stays below enqueue rate, the worker path is the bottleneck

4. `Flashsale Terminalization Outcomes`

- purpose: show whether queued work is eventually succeeding or just retrying forever
- read it like this: compare retry trends, success trends, and worker error trends over the same time window; healthy systems may retry briefly but should converge toward success

## Panel Annotation Style

Every panel description is written as:

- `为什么重要`
- `怎么看`

This is intentional. During perf runs, the dashboards are not just for display; they are meant to guide diagnosis quickly while pressure is happening in real time.

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
