# homelab-cloud

Personal k3s native cloud for platform engineering practice, automate CICD, deployments, infras, agent feedbacks and risks.

## Why This Exists

I use AI to generate a lot of code on misc ideas, and then these problem surfaces.
- what works on your local does not work on production environment
- what happens on your production environment is not exposed to your local thus not available to your agent
- I do not want to spend the same energy provisioning infra for every service.
- I need a real lab where I can organize release between what is stable vs what is not stable written by agent, and i need to expose production metrics to coding agent so it can fix it.

This platform is the result: a shared place where services can converge, agent can write code via github apps, can focus on code, logic, and implementation details, and the infra (which is currently manually in a central way) provisioning plus GitOps work is handled by a centralized platform layer.

## Platform Overview

![homelab-cloud infrastructure overview](docs/infra-overview.svg)

This diagram is intentionally platform-first: it shows how delivery, cluster runtime, cloud dependencies, and the shared control plane fit together, without diving into each microservice internals. The source lives in [docs/infra-overview.d2](docs/infra-overview.d2).

## Start Here

| Page | What it covers |
|---|---|
| [Repository overview](docs/overview.md) | High-level architecture, layout, and shared conventions |
| [Flashsales workload](flashsale/docs/flashsales.md) | Concurrency practice app deployed to the VPS, smoke test, and debugging |
| [Flashsales harness engineering](flashsale/docs/flashsales-harness-engineering.md) | Current flashsales correctness risks, perf harness interpretation, and priority backlog |
| [Flashsales deploy pre](.github/workflows/flashsales-deploy-pre.yml) | Pre-deploy unit and Docker Compose integration gates that do not touch the live k3s deployment |
| [Flashsales deploy](.github/workflows/flashsales-deploy.yml) | Image build, push, and default k3s deployment after pre-gates succeed |
| [Flashsales deploy post](.github/workflows/flashsales-deploy-post.yml) | Post-deploy runtime consistency and performance lanes against the live k3s deployment |
| [Strategy tester workload](docs/strategy-tester.md) | Scheduled ingestion app, cron jobs, and secret wiring |
| [LeetCode intelligence workload](docs/leetcode-intelligence.md) | Continuous intelligence API service with Discord and LLM secret wiring |
| [Infrastructure](docs/infrastructure.md) | Terraform, Neon provisioning, AWS SSM secrets, spot-worker VPC, and state backend |
| [Operations and tooling](docs/operations.md) | CI/CD, perf tests, local workflows, and developer setup |

If you only need one place to orient yourself, start with [Repository overview](docs/overview.md).

## Quick Commands

```bash
make deploy KUBECONFIG_PATH=$HOME/.kube/config
make status KUBECONFIG_PATH=$HOME/.kube/config
make e2e KUBECONFIG_PATH=$HOME/.kube/config
make concurrency-baseline KUBECONFIG_PATH=secrets/.kube-config
make k3s-spot-plan
```

## Repository Layout

```text
.
├── charts/                 # Helm charts for flashsales, strategy-tester, and leetcode-intelligence
├── flashsale/              # FastAPI service sources, local scripts, and perf harnesses for the flashsales workload
├── secrets/                # Local and shared secret material
├── terraform/              # Neon, SSM, low-cost spot network, and k3s spot-node provisioning
├── docs/                   # Split documentation pages
└── Makefile                # Local deployment and maintenance targets
```

For workflow-specific guidance, see [Operations and tooling](docs/operations.md).
