# homelab-cloud

Platform control plane for workload deploys, resource allocation, and runtime performance-test provisioning on a shared k3s environment.

## Why This Exists

I use AI to generate and iterate on a lot of service code, but the hard part is rarely just writing the code.

- local success does not prove k3s deploy success
- production behavior needs to be observable back to the agent
- infra and secrets provisioning should not be rebuilt per app
- performance and correctness lanes need real runtime capacity, not only local mocks

This repository is that shared platform layer. App repos can stay focused on vibe coding and service implementation, while `homelab-cloud` acts as the scheduler that:

- deploys workloads onto k3s
- allocates shared runtime resources such as cluster capacity, secrets, and databases
- provisions the runtime environment used by post-deploy consistency and perf lanes
- closes the loop with logs, metrics, and workflow feedback

## Platform Overview

![homelab-cloud infrastructure overview](docs/infra-overview.svg)

This diagram is intentionally control-plane-first: it shows `homelab-cloud` as the orchestration layer that owns deploy execution, runtime resource allocation, and perf-test environment provisioning. The source lives in [docs/infra-overview.d2](docs/infra-overview.d2).

## What This Repo Schedules

| Control-plane responsibility | What it means here |
|---|---|
| Deploy orchestration | GitHub Actions drives Helm-based rollout into the shared k3s cluster |
| Resource allocation | Terraform and cluster config provision Neon, AWS SSM secrets, and spot-backed worker capacity |
| Runtime perf provisioning | Post-deploy workflows prepare the live runtime needed by flashsale consistency and perf cadence |
| Feedback loop | Workflow logs, Discord notifications, Grafana, and docs feed runtime behavior back into the repo |

## Start Here

| Page | What it covers |
|---|---|
| [Repository overview](docs/overview.md) | High-level architecture, layout, and shared conventions |
| [Flashsales workload](application/flashsale/docs/flashsales.md) | App-owned release contract, k3s deploy path, and runtime perf cadence |
| [Flashsales harness engineering](application/flashsale/docs/flashsales-harness-engineering.md) | Current flashsales correctness risks, perf harness interpretation, and priority backlog |
| [Flashsales deploy pre](application/flashsale/.github/workflows/flashsales-deploy-pre.yml) | App-owned pre-deploy unit and Docker Compose integration gates |
| [Flashsales deploy](.github/workflows/flashsales-deploy.yml) | Platform-side deploy executor for the shared k3s runtime |
| [Flashsales deploy post](.github/workflows/flashsales-deploy-post.yml) | Platform-side runtime consistency and perf provisioner after deploy |
| [Strategy tester workload](docs/strategy-tester.md) | Scheduled ingestion app, cron jobs, and secret wiring |
| [LeetCode intelligence workload](docs/leetcode-intelligence.md) | Continuous intelligence API service with Discord and LLM secret wiring |
| [Infrastructure](docs/infrastructure.md) | Terraform-backed resource provisioning for Neon, SSM, networking, and worker capacity |
| [Operations and tooling](docs/operations.md) | CI/CD, runtime gates, perf workflows, and operator commands |

If you only need one place to orient yourself, start with [Repository overview](docs/overview.md).

## Quick Commands

```bash
make deploy KUBECONFIG_PATH=$HOME/.kube/config
make status KUBECONFIG_PATH=$HOME/.kube/config
make e2e KUBECONFIG_PATH=$HOME/.kube/config
make concurrency-baseline KUBECONFIG_PATH=secrets/.kube-config
make k3s-spot-plan
```

These commands are operator entrypoints into the same control plane:

- `make deploy`: reconcile a workload release into k3s
- `make status`: inspect live runtime state
- `make e2e`: exercise the deployed path
- `make concurrency-baseline`: provision and run a baseline perf lane
- `make k3s-spot-plan`: inspect worker-capacity allocation changes

## Repository Layout

```text
.
├── .github/workflows/      # Deploy, post-deploy runtime gates, and infra automation entrypoints
├── .github/scripts/        # Workflow-side orchestration helpers
├── charts/                 # Helm release definitions for platform-managed workloads
├── application/flashsale/              # App submodule plus quality contract and perf harness inputs
├── secrets/                # Local and shared secret material
├── terraform/              # Resource allocation for Neon, SSM, networking, and spot-backed capacity
├── docs/                   # Platform docs and control-plane diagrams
└── Makefile                # Operator-facing deploy and diagnostics commands
```

For workflow-specific guidance, see [Operations and tooling](docs/operations.md).
