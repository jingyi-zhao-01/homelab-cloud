# Operations and Tooling

This page collects the operational commands and workflow details that used to be buried in the root README.

## CI/CD

| Workflow | Trigger | Scope |
| --- | --- | --- |
| `application/flashsale/.github/workflows/flashsales-deploy-pre.yml` | Pushes or PRs in the standalone `flashsale` repo | Flashsales pre-deploy gates |
| `flashsales-deploy.yml` | Pushes to `flashsale`, `.gitmodules`, or `charts/flashsales/**`, or manual dispatch | Flashsales deploy |
| `flashsales-deploy-post.yml` | After a successful `flashsales-deploy.yml` or manual dispatch | Unified flashsales post-deploy quality gate |
| `deploy-strategy-tester.yml` | Pushes to `strategy-tester/**` or `charts/strategy-tester/**` | Strategy tester |
| `deploy-leetcode-intelligence.yml` | Pushes to `charts/leetcode-intelligence/**` | LeetCode intelligence |
| `flashsales-loadtest-manual.yml` | Manual `workflow_dispatch` | Performance testing |
| `terraform-provision.yml` | Manual | Neon and SSM infrastructure provisioning |
| `terraform-k3s-spot-network.yml` | Manual | Low-cost VPC and public subnets for the spot worker |
| `terraform-k3s-spot-node.yml` | Manual | One self-healing AWS spot k3s worker |

The deploy workflows are independent, so changes to one workload should not trigger the other.

## Required Secrets

```text
KUBE_CONFIG_DATA
GHCR_PULL_USERNAME
GHCR_PULL_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

`GHCR_PULL_TOKEN` must be able to read private packages in GHCR. In practice that means a classic PAT with `read:packages`, or an equivalent fine-grained token scoped to the repository packages that back the flashsales images.

## Performance Testing

Perf runs currently execute the ordered cadence declared by `application/flashsale/release/flashsale-quality-contract.yaml`; the platform workflow provides runner, kubeconfig, and cluster access, but does not hardcode the lane order.

For the current interpretation limits and correctness caveats of the flashsales perf harness, use [Flashsales harness engineering](../application/flashsale/docs/flashsales-harness-engineering.md) as the source of truth.

```bash
make concurrency-baseline KUBECONFIG_PATH=secrets/.kube-config
make concurrency-smoke KUBECONFIG_PATH=secrets/.kube-config
make concurrency-hotspot-10tps KUBECONFIG_PATH=secrets/.kube-config
bash ./application/flashsale/perf/scripts/loadtest-k6.sh -e RAMP_UP=30s -e STEADY=180s -e TARGET_VUS=50
```

## Developer Setup

```bash
git submodule update --init --recursive
cd application/flashsale
uv sync --extra dev
uv run pre-commit install
```

The repo uses pre-commit hooks for whitespace, end-of-file, YAML checks, Helm linting, and shared `pylint` checks for the flashsale microservices.

## Lint Standard

- `pylint` is the shared development linter for the three flashsale microservices.
- The shared rule currently enforced is `too-many-lines`, with `max-module-lines = 500`.
- If a Python module approaches the limit, split it by responsibility instead of appending another large section.
- The shared lint hook runs against `app/` and `tests/` modules in `user-service`, `product-service`, and `order-service`.
- Run `make lint` before pushing when you touch multiple files or refactor large modules.

## Terraform-Backed Infrastructure

The current k3s setup relies on Terraform-provisioned AWS SSM parameters for secrets delivery, Terraform can also maintain one AWS spot-backed k3s worker, and Terraform state is stored in an S3 bucket configured at init time.

For the unified flashsale infrastructure entrypoint and the Neon/secrets workflow details, see [Infrastructure](infrastructure.md).

For Grafana provisioning related to the flashsale async reservation path, use:

- [terraform/flashsale](../terraform/flashsale/README.md)
- [terraform/flashsale-grafana-dashboards](../terraform/flashsale-grafana-dashboards/README.md)

Automatic provisioning entrypoint:

- `.github/workflows/terraform-flashsale-grafana-dashboards.yml`

Important datasource note:

- the flashsale Grafana dashboard module expects a Grafana `PostgreSQL` datasource backed by Neon
- this is represented in Terraform as `neon_datasource_uid`
- Loki remains a separate datasource via `loki_datasource_uid`

Required GitHub configuration for auto-apply:

- Secret: `GRAFANA_AUTH`
- Variable: `GRAFANA_URL`
- Variable: `FLASHSALE_GRAFANA_NEON_DATASOURCE_UID`
- Variable: `FLASHSALE_GRAFANA_LOKI_DATASOURCE_UID`

The workflow auto-applies on pushes to `main` when files under `terraform/flashsale-grafana-dashboards/**` change.

If flashsale is configured to read Redis credentials from AWS SSM through External Secrets, enable both of these Helm values:

- `externalSecrets.enabled=true`
- `externalSecrets.includeUpstashRedis=true`

For remote spot workers, do not stop at `k3s_server_url` and `k3s_token`. Make sure the worker Terraform inputs also include `trusted_cluster_cidrs` so the control-plane, VPN, or other trusted cluster paths can actually reach the node for cross-node networking and monitoring.

The reusable workflow pair is:

- `terraform-k3s-spot-network-internal.yml` for the VPC and public subnets
- `terraform-k3s-spot-node-internal.yml` for the worker itself

The manual entrypoint is `terraform-k3s-spot-node.yml`, and the most important remote-worker inputs are `trusted_cluster_cidrs` plus optional `extra_k3s_agent_args`.

After a successful spot-node `apply`, the top-level workflow can also reconcile the cluster-level `grafana-k8s-monitoring` Helm release. This is the preferred automation shape for Alloy-based monitoring:

- the EC2 bootstrap only has to join k3s successfully
- the monitoring stack stays managed as a Kubernetes Helm release instead of a node-local install
- when a new spot worker becomes `Ready`, the chart-managed DaemonSet collectors can land on it automatically

Use the `reconcile_grafana_monitoring` workflow input if you need to disable that post-apply reconcile for a specific run.

## Spot Worker Tailscale Bootstrap

The spot-worker workflow can bootstrap each new worker directly into your Tailscale network before k3s starts. This is the recommended path when the control-plane already lives on Tailscale and the worker would otherwise join across a mixed public/private network boundary.

Recommended GitHub configuration:

- Secret: `TS_SPOT_AUTH_KEY`
  Use a pre-auth Tailscale auth key intended for the spot worker bootstrap. Prefer an ephemeral or reusable tagged key with the minimum tailnet permissions needed.
- Variable: `K3S_SERVER_URL_TAILSCALE`
  Set this to the control-plane Tailscale API endpoint, for example `https://100.92.165.80:6443`.
- Variable: `K3S_SPOT_ENABLE_TAILSCALE`
  Set this to `true` if you want the internal reusable workflow default to enable Tailscale bootstrap.
- Variable: `K3S_SPOT_TAILSCALE_TAGS`
  Optional comma-separated tags such as `tag:k3s,tag:spot`.

When Tailscale bootstrap is enabled, the worker user-data does the following:

- installs `tailscaled`
- joins the tailnet with `TS_SPOT_AUTH_KEY`
- reads the worker's Tailscale IPv4 address
- uses that Tailscale address for `--node-ip` and `--node-external-ip`
- forces flannel to bind to `tailscale0` so the pod overlay does not fall back to the AWS/private NIC

That usually gives more stable kubelet scraping, CoreDNS reachability, and Grafana Alloy connectivity than mixing the home control-plane public IP with the AWS worker private IP.

Important: the control-plane must match this and run k3s with `flannel-iface: tailscale0` too. If only the worker uses Tailscale while the server-side flannel backend still advertises a public or AWS-local IP, nodes may show `Ready` while cross-node pod traffic, CoreDNS lookups, and ingress paths still time out.

## Private Network Access For Public GitHub Actions

If you want to keep using GitHub-hosted runners, the recommended path is to connect those runners to your private cluster network instead of exposing deploy reliability to the public `6443` endpoint.

The flashsales deploy, runtime consistency, and perf workflows support these repository variables/secrets for this:

- `K8S_RUNNER_LABELS_JSON`
- `K3S_SERVER_URL_TAILSCALE`
- `TS_CI_TAGS`

And the following repository secrets when using Tailscale OAuth:

- `TS_OAUTH_CLIENT_ID`
- `TS_OAUTH_SECRET`

Recommended setup:

1. Put the k3s control-plane machine on Tailscale.
2. Create a reusable tagged OAuth client for GitHub Actions in Tailscale, and make sure the ephemeral CI nodes can reach the control-plane.
3. Store `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_SECRET` as repository secrets.
4. Set `TS_CI_TAGS` to something like `tag:ci`.
5. Set `K3S_SERVER_URL_TAILSCALE` to the Tailscale URL for the control-plane, for example `https://100.x.y.z:6443`.
6. Leave `K8S_RUNNER_LABELS_JSON` unset if you want to stay on GitHub-hosted runners.

The workflows still read `KUBE_CONFIG_DATA`, but when `K3S_SERVER_URL_TAILSCALE` is set they rewrite the active cluster server in that kubeconfig before running `kubectl`.

This is the preferred path when:

- the k3s API server is on a home ISP connection
- inbound `6443` is occasionally unreachable from GitHub-hosted runners
- you want to keep using public GitHub Actions runners

If you later decide to move the k8s-touching jobs onto a self-hosted runner, `K8S_RUNNER_LABELS_JSON` can still point those workflows at labels such as `["self-hosted","linux","x64","homelab-k3s"]`.

Local state is not a supported operating mode. Use the GitHub workflows or pass `TF_STATE_BUCKET` and `AWS_REGION` so local Make targets initialize the S3 backend explicitly.

## Useful Make Targets

| Target | Purpose |
| --- | --- |
| `make deploy` | Deploy flashsales to the configured cluster |
| `make status` | Show pods and services |
| `make fix-images` | Rebuild, import, restart, and verify flashsales images |
| `make e2e` | Run the flashsales smoke test |
| `make neon-plan` | Preview Neon Terraform changes using remote S3 state |
| `make neon-apply` | Provision Neon resources through Terraform using remote S3 state |
| `make k3s-network-plan` | Preview the low-cost VPC and public subnet stack for the spot worker |
| `make k3s-network-apply` | Create or reconcile the low-cost VPC and public subnet stack |
| `make k3s-spot-plan` | Preview the AWS spot-backed k3s worker Terraform changes |
| `make k3s-spot-apply` | Create or reconcile one self-healing AWS spot-backed k3s worker using remote S3 state |

## Related Pages

- [Repository overview](overview.md)
- [Infrastructure](infrastructure.md)
- [Flashsales workload](../application/flashsale/docs/flashsales.md)
- [Flashsale Grafana dashboards](../terraform/flashsale-grafana-dashboards/README.md)
- [Strategy tester workload](strategy-tester.md)
- [LeetCode intelligence workload](leetcode-intelligence.md)

Back to [README](../README.md).
