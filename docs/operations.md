# Operations and Tooling

This page collects the operational commands and workflow details that used to be buried in the root README.

## CI/CD

| Workflow | Trigger | Scope |
|---|---|---|
| `deploy-flashsale.yml` | Pushes to `flashsale/**` or `charts/flashsales/**` | Flashsales |
| `deploy-strategy-tester.yml` | Pushes to `strategy-tester/**` or `charts/strategy-tester/**` | Strategy tester |
| `perf-concurrency-suite.yml` | After a successful flashsales deploy | Concurrency suite |
| `loadtest-manual.yml` | Manual `workflow_dispatch` | Performance testing |
| `terraform-provision.yml` | Manual | Infrastructure provisioning |

The deploy workflows are independent, so changes to one workload should not trigger the other.

## Required Secrets

```text
KUBE_CONFIG_DATA
GHCR_PULL_USERNAME
GHCR_PULL_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

## Performance Testing

Perf runs currently provision an ephemeral Neon database through Terraform before the load test executes.

```bash
make loadtest KUBECONFIG_PATH=secrets/.kube-config
make loadtest-lite KUBECONFIG_PATH=secrets/.kube-config
bash ./perf/loadtest-k6.sh -e RAMP_UP=30s -e STEADY=180s -e TARGET_VUS=50
```

## Developer Setup

```bash
uv sync --extra dev
uv run pre-commit install
```

The repo uses pre-commit hooks for whitespace, end-of-file, YAML checks, and Helm linting.

## Terraform-Backed Infrastructure

The current k3s setup relies on Terraform-provisioned AWS SSM parameters for secrets delivery, and Terraform state is stored in an S3 bucket configured at init time.

For the Neon and secrets workflow details, see [Infrastructure](infrastructure.md).

## Useful Make Targets

| Target | Purpose |
|---|---|
| `make deploy` | Deploy flashsales to the configured cluster |
| `make status` | Show pods and services |
| `make fix-images` | Rebuild, import, restart, and verify flashsales images |
| `make e2e` | Run the flashsales smoke test |
| `make neon-apply` | Provision Neon resources through Terraform |

## Related Pages

- [Repository overview](overview.md)
- [Infrastructure](infrastructure.md)
- [Flashsales workload](flashsales.md)
- [Strategy tester workload](strategy-tester.md)

Back to [README](../README.md).
