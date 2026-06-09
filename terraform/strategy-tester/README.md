# Strategy Tester Grafana Dashboards

This Terraform root module provisions Grafana dashboards for the `strategy-tester` stack.

## Scope

The initial dashboard in this directory focuses on one thing:

- automatically rendering volatility surfaces for every underlying asset currently present in the `options` table

It uses a hidden Grafana query variable to enumerate all `underlying_ticker` values from PostgreSQL and repeats a Plotly panel once per asset, so the dashboard auto-expands as new underlyings appear in the dataset.

## Requirements

- a PostgreSQL datasource in Grafana that points at the `strategy-tester` Neon database
- the Grafana Plotly panel plugin `ae3e-plotly-panel` enabled on the target Grafana instance

## Example

```bash
cd terraform/strategy-tester
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=strategy-tester/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="encrypt=true"
terraform plan
terraform apply
```

## Required Inputs

- `grafana_url`
- `grafana_auth`
- `neon_datasource_uid`

See [terraform.tfvars.example](./terraform.tfvars.example) for a starting point.
