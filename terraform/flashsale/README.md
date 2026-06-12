# Flashsale Terraform Stack

This directory is the unified Terraform entrypoint for flashsale infrastructure.

It composes the flashsale-specific pieces that used to live in separate directories:

- Neon PostgreSQL provisioning
- Grafana dashboard provisioning
- Upstash Redis provisioning
- AWS SSM Parameter Store secret sync

## Scope

The stack currently manages:

- a Neon project for the shared flashsale PostgreSQL database
- the Grafana folder and dashboards for flashsale observability
- an Upstash Redis database suitable for `order-service` caching, idempotency, or queue-adjacent coordination
- SSM `SecureString` parameters for database and Upstash connection material

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
- `aws_region`

See [terraform.tfvars.example](./terraform.tfvars.example) for a working starting point.

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

## Notes

- The Neon and Grafana subdirectories still exist for compatibility, but the preferred automation entrypoint is the namespace-level flashsale stack and its `terraform-flashsale-resources.yml` workflow.
- The Upstash provider stores connection outputs in Terraform state. Treat remote state access as sensitive.
- The stack now mirrors both Neon and Upstash credentials into AWS SSM Parameter Store under `/flashsales/prod` by default.
- The SSM path includes `DATABASE_URL`, `POSTGRES_*`, `REDIS_URL`, `UPSTASH_REDIS_ENDPOINT`, `UPSTASH_REDIS_PASSWORD`, `UPSTASH_REDIS_REST_TOKEN`, and `UPSTASH_REDIS_READ_ONLY_REST_TOKEN`.
