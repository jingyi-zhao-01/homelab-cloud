# Infrastructure

This repository uses Terraform as the control plane for the shared platform pieces that sit underneath both workloads.

## What Terraform Manages

- An ephemeral Neon database is provisioned for the flashsales performance test workflow.
- The k3s workloads rely on Terraform-provisioned AWS SSM parameters to store and distribute secrets.
- A dedicated AWS Auto Scaling Group can keep one k3s worker alive on Spot capacity and automatically replace it after reclamation.
- The Terraform workflows use an S3 backend for state, with the bucket supplied at init time.

## Neon Flow

The `terraform/neon` stack provisions the Neon project and writes the resulting credentials into the Kubernetes Secret expected by the flashsales chart.

The follow-up `terraform/ssm` stack syncs those same credentials into AWS SSM Parameter Store so both workloads can consume them through External Secrets Operator.

## Spot Worker Flow

The `terraform/k3s-spot-node` stack creates a launch template plus an Auto Scaling Group with `min=1`, `max=1`, and `desired=1` on Spot capacity only.

That shape gives you exactly one EC2 worker under normal conditions, and if AWS reclaims the instance the Auto Scaling Group immediately tries to launch a replacement from the same template.

The instance bootstraps itself as a `k3s agent` and joins the existing server using the supplied server URL and token.

The stack expects you to provide existing network inputs such as `vpc_id`, `subnet_ids`, `k3s_server_url`, and `k3s_token`. See [terraform/k3s-spot-node/terraform.tfvars.example](../terraform/k3s-spot-node/terraform.tfvars.example) for the local input shape.

## State and Backends

Terraform state is not kept locally as the source of truth. The workflow configures an S3 backend, and CI passes the bucket name through `TF_STATE_BUCKET`.

That setup keeps the Neon and SSM stacks aligned across apply, plan, and destroy operations.

The repository Make targets are also expected to use the same remote S3 backend. Local Terraform state is intentionally unsupported.

## What Does Not Happen In-Cluster

The current setup does not run Terraform from inside k3s, and k3s itself is not the Terraform control plane.

Today the control loop is:

- Terraform state lives in S3.
- Terraform runs from GitHub Actions or a local shell that is explicitly configured to use that remote S3 backend.
- The k3s cluster consumes the results, but it does not reconcile Terraform resources on its own.

If you want the cluster itself to own cloud infrastructure changes, that is a different design and would require an in-cluster controller such as Crossplane or a Terraform controller.

## Related Pages

- [Repository overview](overview.md)
- [Operations and tooling](operations.md)

Back to [README](../README.md).
