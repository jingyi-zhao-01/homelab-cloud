# homelab-cloud

Personal k3s homelab for platform engineering practice, split into two independently deployed workloads.

## Start Here

| Page | What it covers |
|---|---|
| [Repository overview](docs/overview.md) | High-level architecture, layout, and shared conventions |
| [Flashsales workload](docs/flashsales.md) | Concurrency practice app, local deploy, smoke test, and debugging |
| [Strategy tester workload](docs/strategy-tester.md) | Scheduled ingestion app, cron jobs, and secret wiring |
| [Infrastructure](docs/infrastructure.md) | Terraform, Neon provisioning, AWS SSM secrets, and state backend |
| [Operations and tooling](docs/operations.md) | CI/CD, perf tests, local workflows, and developer setup |

If you only need one place to orient yourself, start with [Repository overview](docs/overview.md).

## Quick Commands

```bash
make deploy KUBECONFIG_PATH=$HOME/.kube/config
make status KUBECONFIG_PATH=$HOME/.kube/config
make e2e KUBECONFIG_PATH=$HOME/.kube/config
make loadtest KUBECONFIG_PATH=secrets/.kube-config
```

## Repository Layout

```text
.
├── charts/                 # Helm charts for flashsales and strategy-tester
├── flashsale/              # FastAPI service sources for the flashsales workload
├── perf/                   # k6 load test scripts and helpers
├── scripts/                # Smoke tests and local automation
├── secrets/                # Local and shared secret material
├── terraform/              # Neon and SSM provisioning
├── docs/                   # Split documentation pages
└── Makefile                # Local deployment and maintenance targets
```

For workflow-specific guidance, see [Operations and tooling](docs/operations.md).
