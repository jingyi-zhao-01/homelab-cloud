# Operations and Tooling

This page collects the operational commands and workflow details that used to be buried in the root README.

## CI/CD

| Workflow | Trigger | Scope |
| --- | --- | --- |
| `flashsales-deploy-pre.yml` | Pushes to `flashsale/**` or `charts/flashsales/**` | Flashsales pre-deploy gates |
| `flashsales-deploy.yml` | After a successful `flashsales-deploy-pre.yml` or manual dispatch | Flashsales deploy |
| `flashsales-deploy-post.yml` | After a successful `flashsales-deploy.yml` or manual dispatch | Flashsales post-deploy runtime consistency and perf |
| `deploy-strategy-tester.yml` | Pushes to `strategy-tester/**` or `charts/strategy-tester/**` | Strategy tester |
| `deploy-leetcode-intelligence.yml` | Pushes to `charts/leetcode-intelligence/**` | LeetCode intelligence |
| `flashsales-perf-concurrency-suite.yml` | Manual or reusable via `flashsales-deploy-post.yml` | Concurrency suite |
| `flashsales-loadtest-manual.yml` | Manual `workflow_dispatch` | Performance testing |
| `terraform-provision.yml` | Manual | Neon and SSM infrastructure provisioning |
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

Perf runs currently provision an ephemeral Neon database through Terraform before the load test executes.

For the current interpretation limits and correctness caveats of the flashsales perf harness, use [Flashsales harness engineering](../flashsale/docs/flashsales-harness-engineering.md) as the source of truth.

```bash
make concurrency-baseline KUBECONFIG_PATH=secrets/.kube-config
make concurrency-smoke KUBECONFIG_PATH=secrets/.kube-config
bash ./flashsale/perf/scripts/loadtest-k6.sh -e RAMP_UP=30s -e STEADY=180s -e TARGET_VUS=50
```

## Developer Setup

```bash
cd flashsale
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

For the Neon and secrets workflow details, see [Infrastructure](infrastructure.md).

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
| `make k3s-spot-plan` | Preview the AWS spot-backed k3s worker Terraform changes |
| `make k3s-spot-apply` | Create or reconcile one self-healing AWS spot-backed k3s worker using remote S3 state |

## Related Pages

- [Repository overview](overview.md)
- [Infrastructure](infrastructure.md)
- [Flashsales workload](../flashsale/docs/flashsales.md)
- [Strategy tester workload](strategy-tester.md)
- [LeetCode intelligence workload](leetcode-intelligence.md)

Back to [README](../README.md).
