# Infrastructure

This repository uses Terraform as the control plane for the shared platform pieces that sit underneath both workloads.

## What Terraform Manages

- An ephemeral Neon database is provisioned for the flashsales performance test workflow.
- The k3s workloads rely on Terraform-provisioned AWS SSM parameters to store and distribute secrets.
- The Terraform workflows use an S3 backend for state, with the bucket supplied at init time.

## Neon Flow

The `terraform/neon` stack provisions the Neon project and writes the resulting credentials into the Kubernetes Secret expected by the flashsales chart.

The follow-up `terraform/ssm` stack syncs those same credentials into AWS SSM Parameter Store so both workloads can consume them through External Secrets Operator.

## State and Backends

Terraform state is not kept locally as the source of truth. The workflow configures an S3 backend, and CI passes the bucket name through `TF_STATE_BUCKET`.

That setup keeps the Neon and SSM stacks aligned across apply, plan, and destroy operations.

## Related Pages

- [Repository overview](overview.md)
- [Operations and tooling](operations.md)

Back to [README](../README.md).
