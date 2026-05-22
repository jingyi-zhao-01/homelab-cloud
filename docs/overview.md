# Repository Overview

This repository is a personal Kubernetes homelab centered on three independent workloads:

## Why This Exists

I rely on AI to generate a lot of dev-level code, but I do not want to provision infrastructure for every service by hand. I also wanted a real-world lab where I can experiment with system design ideas instead of keeping them only in books.

This platform gives me a centralized layer where services can converge. The service layer can focus on code, logic, and implementation, while infra provisioning and GitOps are handled by the platform layer.

| Namespace | Purpose |
|---|---|
| `flashsales` | Concurrency practice workload with three FastAPI services and self-hosted supporting data stores |
| `strategy-tester` | Scheduled ingestion workload driven by cron jobs and external secrets |
| `leetcode-intelligence` | Continuous API workload for prompt dispatch, reply scoring, and focus recommendations |

## Shared Shape

- Helm charts live under `charts/` and are deployed independently per namespace.
- FastAPI service source for the flashsales workload lives under `flashsale/`.
- Performance experiments and smoke tests live under `perf/` and `scripts/`.
- Terraform in `terraform/` provisions Neon, AWS SSM-backed secrets, and related infrastructure.
- Secret material is kept under `secrets/` and is treated as environment-specific.

## Conventions

| Area | Convention |
|---|---|
| Image tags | `values.yaml` is the source of truth for deployed image references |
| Chart versioning | Helm chart version changes should stay separate from image tag changes unless both are intentional |
| Deploy scope | Flashsales and strategy-tester deploy independently and should not trigger each other |
| Local safety | Local deployment is intended for k3s on localhost, not arbitrary remote clusters |

## Related Pages

- [Infrastructure](infrastructure.md)
- [Flashsales workload](flashsales.md)
- [Strategy tester workload](strategy-tester.md)
- [Operations and tooling](operations.md)
- [LeetCode intelligence workload](leetcode-intelligence.md)

Back to [README](../README.md).
