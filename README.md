# homelab-cloud

Personal k3s native cloud for platform engineering practice, automate CICD, deployments, infras, agent feedbacks and risks.

## Why This Exists

I use AI to generate a lot of code on misc ideas, and then these problem surfaces. 
- what works on your local does not work on production environment
- what happens on your production environment is not exposed to your local thus not available to your agent
- I do not want to spend the same energy provisioning infra for every service.
- I need a real lab where I can organize release between what is stable vs what is not stable written by agent, and i need to expose production metrics to coding agent so it can fix it. 

This platform is the result: a shared place where services can converge, agent can write code via github apps, can focus on code, logic, and implementation details, and the infra (which is currently manually in a central way) provisioning plus GitOps work is handled by a centralized platform layer.

## Start Here

| Page | What it covers |
|---|---|
| [Repository overview](docs/overview.md) | High-level architecture, layout, and shared conventions |
| [Flashsales workload](docs/flashsales.md) | Concurrency practice app deployed to the VPS, smoke test, and debugging |
| [Strategy tester workload](docs/strategy-tester.md) | Scheduled ingestion app, cron jobs, and secret wiring |
| [LeetCode intelligence workload](docs/leetcode-intelligence.md) | Continuous intelligence API service with Discord and LLM secret wiring |
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
├── charts/                 # Helm charts for flashsales, strategy-tester, and leetcode-intelligence
├── flashsale/              # FastAPI service sources for the flashsales workload
├── perf/                   # k6 load test scripts and helpers
├── scripts/                # Smoke tests and local automation
├── secrets/                # Local and shared secret material
├── terraform/              # Neon and SSM provisioning
├── docs/                   # Split documentation pages
└── Makefile                # Local deployment and maintenance targets
```

For workflow-specific guidance, see [Operations and tooling](docs/operations.md).
