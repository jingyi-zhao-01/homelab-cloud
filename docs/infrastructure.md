# Infrastructure

This repository uses Terraform as the control plane for the shared platform pieces that sit underneath both workloads.

## What Terraform Manages

- An ephemeral Neon database is provisioned for the flashsales performance test workflow.
- The k3s workloads rely on Terraform-provisioned AWS SSM parameters to store and distribute secrets.
- A dedicated low-cost VPC with public subnets can be provisioned for the AWS spot-backed k3s worker without adding a NAT gateway.
- A dedicated AWS Auto Scaling Group can keep one k3s worker alive on Spot capacity and automatically replace it after reclamation.
- The Terraform workflows use an S3 backend for state, with the bucket supplied at init time.

## Spot Network Flow

The `terraform/k3s-spot-network` stack provisions a minimal VPC, an internet gateway, a public route table, and public subnets across multiple availability zones.

It is intentionally the cheapest usable network shape for this repo: no NAT gateway, no private subnets, and no always-on managed network appliances.

That keeps the network layer itself in the near-zero-cost bucket, but EC2 public IPv4 charges and normal data transfer charges still apply.

## Flashsale Infrastructure Flow

The preferred flashsale Terraform entrypoint is `terraform/flashsale`.

That aggregate stack currently groups three flashsale-specific infrastructure surfaces:

- Neon for the shared PostgreSQL database
- Grafana dashboards for flashsale observability
- Upstash Redis for flashsale runtime coordination

The legacy `terraform/neon` stack still exists for backward compatibility and Neon-only workflows.

The aggregate `terraform/flashsale` stack now also mirrors runtime secrets into AWS SSM Parameter Store so workloads can consume them through External Secrets Operator.

That SSM surface includes:

- Neon database credentials such as `DATABASE_URL` and `POSTGRES_*`
- Upstash Redis connection material such as `REDIS_URL`
- Upstash REST tokens for future worker or admin flows

## Spot Worker Flow

The `terraform/k3s-spot-node` stack creates a launch template plus an Auto Scaling Group with `min=1`, `max=1`, and `desired=1` on Spot capacity only.

That shape gives you exactly one EC2 worker under normal conditions, and if AWS reclaims the instance the Auto Scaling Group immediately tries to launch a replacement from the same template.

The instance bootstraps itself as a `k3s agent` and joins the existing server using the supplied server URL and token.

The stack can either consume explicit `vpc_id` and `subnet_ids`, or it can automatically reuse the remote state from `terraform/k3s-spot-network` in the same S3 bucket. See [terraform/k3s-spot-node/terraform.tfvars.example](../terraform/k3s-spot-node/terraform.tfvars.example) for the local input shape.

### Networking Caveat For Remote Workers

If the k3s server and the AWS spot worker do not share the same directly reachable private network, the worker security group must explicitly trust the CIDRs that carry cluster traffic.

Use `trusted_cluster_cidrs` for the control-plane public IP, VPN CIDR, or other trusted ingress ranges that need to reach the worker for overlay networking, node-to-node traffic, and host-level scrapes such as `node-exporter`.

If you drive the worker stack from GitHub Actions, pass the same ranges through the `trusted_cluster_cidrs` input on `terraform-k3s-spot-node.yml` or the reusable `terraform-k3s-spot-node-internal.yml` workflow.

Without that ingress, the worker may still appear `Ready`, but cross-node pod traffic and node observability can fail in subtle ways, for example:

- worker pods timing out when they resolve `CoreDNS`
- `node-exporter` on the worker being healthy locally but unreachable from the metrics collector
- Grafana listing the node while CPU and memory usage remain `No data`

For clusters that span multiple networks or public IPs, the k3s server side should also follow the official multicloud guidance for external node addresses and Flannel external-IP routing.

For GitHub Actions based deploys and runtime gates, the most reliable operating mode is a private network path to the control-plane. In practice, that usually means GitHub-hosted runners joining your Tailscale tailnet during the workflow, or a self-hosted runner with private/VPN reachability. In both cases, the kubeconfig server override should point at the private endpoint instead of the public API address.

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
