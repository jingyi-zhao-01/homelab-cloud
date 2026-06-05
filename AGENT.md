# AGENTS.md

## Project Context

This repository is a homelab/cloud infrastructure and workload repo.

Primary workloads:

* `flashsale/`: Git submodule that contains the standalone FastAPI microservice repo for concurrency/system-design practice.
* `charts/flashsales/`: Helm chart for the flashsale workload.
* `terraform/`: Infrastructure provisioning for Neon, AWS SSM, Grafana dashboards, k3s spot workers, and related cloud resources.
* `.github/workflows/`: CI/CD, deploy, post-deploy validation, k6 performance tests, and Terraform automation.

Flashsale services:

* `flashsale/user-service`: user persistence and lookup.
* `flashsale/product-service`: product catalog, stock management, and reservation lifecycle.
* `flashsale/order-service`: order creation, user validation, reserve orchestration, and order persistence.

The flashsale workload is deployed to a VPS-backed k3s cluster, not a local-only environment.

## Agent Operating Rules

### General

* Prefer minimal, focused diffs.
* Do not rewrite unrelated files.
* Do not rename public interfaces, workflow names, Helm values, Terraform variables, or Kubernetes resource names unless the task explicitly requires it.
* Before making a broad refactor, identify the exact files that need to change and explain why.
* Do not scan the whole repo by default. Start from the smallest relevant directory.
* Preserve existing Make targets, workflow entrypoints, and documented operational commands.
* For flashsale changes, record the change in `docs/wiki` in the same turn whenever feasible.
* If you add or modify an ADR, mirror the reader-facing copy in `docs/wiki/adrs` and keep the repo ADR as the engineering source of truth.
* Treat `docs/wiki` as the operational narrative for what changed, why it changed, and how to verify it.

### Safety Rules

* Do not run destructive commands without explicit approval.
* Do not run `kubectl delete`, `terraform destroy`, `helm uninstall`, or destructive database commands unless explicitly requested.
* For Terraform changes, prefer `terraform plan` / existing `make *-plan` targets before any apply.
* For Kubernetes changes, prefer `helm template`, `helm lint`, `kubectl diff`, or dry-run style validation before changing live resources.
* Do not print, commit, or expose secrets.
* Treat GitHub secrets, Kubernetes secrets, kubeconfig, Tailscale keys, Grafana tokens, Neon credentials, and AWS credentials as sensitive.

## Flashsale Architecture Rules

### Current State Machines

Inventory reservation lifecycle:

* `reserve`
* `confirm`
* `cancel`
* `expire`

Order lifecycle:

* `pending`
* `confirmed`
* `failed`
* `expired`

Order requests may include:

* `idempotency_key`
* default-success internal `payment_status`
* pending-order timeout cleanup through `/admin/expire-orders`

When changing order or inventory behavior, preserve idempotency and consistency semantics.

### Service Responsibility Boundaries

Use these defaults unless the issue says otherwise:

* User lookup and user persistence belong in `user-service`.
* Product stock and reservation lifecycle belong in `product-service`.
* Order creation, user validation, reservation orchestration, and order persistence belong in `order-service`.

Do not move business responsibility between services without documenting the reason.

### Synchronous vs Async Reservation Path

The order request path should stay as small as possible.

When investigating order timeout, high p95/p99, or hotspot contention:

1. Check whether `confirm` / `cancel` is still on the synchronous request path.
2. Check DB lock contention and transaction boundaries.
3. Check whether client timeout is being confused with backend cancellation.
4. Check whether late `confirm` / `cancel` can race with teardown, reset, or expiry.
5. Check worker/backlog metrics if terminalization is async.

Do not assume Redis, RabbitMQ, more pods, or spot workers fix the bottleneck until the bottleneck is identified.

## Performance and Correctness Rules

The k6 performance harness is useful for:

* HTTP status behavior.
* broad latency bands.
* 5xx spikes.
* contention and tail-latency trends.

The k6 performance harness is not sufficient for proving:

* stock/order consistency.
* timeout-race behavior.
* order persistence failure windows.
* correctness after partial failures.

For correctness-sensitive changes, use the consistency harness in addition to perf tests.

Preferred verification after flashsale changes:

```bash
bash ./flashsale/scripts/e2e-smoke.sh
make concurrency-smoke
make concurrency-hotspot-10tps
make concurrency-baseline
make concurrency-hotspot
```

For correctness-sensitive changes:

```bash
python3 ./flashsale/perf/python/consistency_harness.py
```

## CI/CD Rules

Respect the existing gate separation:

* `flashsale/.github/workflows/flashsales-deploy-pre.yml`: app-owned pre-deploy unit, Docker Compose integration, contract, lifecycle, timeout-race, DB migration compatibility gates.
* `flashsales-deploy.yml`: k3s deploy after pre-deploy succeeds.
* `flashsales-deploy-post.yml`: runtime consistency and perf validation after deploy.
* `flashsales-consistency.yml`: reusable runtime consistency workflow.
* `flashsales-perf-concurrency-suite.yml`: reusable performance workflow.
* `terraform-provision.yml`: Neon and SSM provisioning.
* `terraform-k3s-spot-network.yml`: low-cost VPC and subnet provisioning for spot worker.
* `terraform-k3s-spot-node.yml`: one self-healing AWS spot k3s worker.

Changes to one workload should not trigger unrelated workload deploys.

## Development Commands

For flashsale development:

```bash
git submodule update --init --recursive
cd flashsale
uv sync --extra dev
uv run pre-commit install
```

Before pushing larger changes:

```bash
make lint
```

The repo uses pre-commit hooks for whitespace, end-of-file, YAML checks, Helm linting, and shared `pylint`.

Python modules should stay below the configured module length limit. If a module is approaching the limit, split by responsibility instead of appending another large section.

## Infrastructure Rules

Terraform-backed infrastructure includes:

* AWS SSM parameters for secrets delivery.
* S3-backed Terraform state.
* Neon database provisioning.
* Grafana dashboard provisioning.
* AWS spot-backed k3s worker provisioning.

Local Terraform state is not a supported operating mode. Use GitHub workflows or initialize the S3 backend explicitly through the documented Make targets.

For Grafana dashboard provisioning:

* Grafana auth is stored as `GRAFANA_AUTH`.
* Grafana URL is stored as `GRAFANA_URL`.
* Neon datasource UID is stored as `FLASHSALE_GRAFANA_NEON_DATASOURCE_UID`.
* Loki datasource UID is stored as `FLASHSALE_GRAFANA_LOKI_DATASOURCE_UID`.

Do not hardcode datasource UIDs, Grafana tokens, Neon credentials, or kubeconfig values.

## Kubernetes and k3s Rules

The cluster is a k3s homelab/VPS setup.

When changing Helm or Kubernetes behavior:

* Prefer `charts/flashsales` as the deployment source of truth.
* Keep resource requests and limits explicit where HPA depends on CPU utilization.
* Do not assume HPA works correctly if CPU requests are missing.
* Treat ingress, readiness, liveness, HPA, and DB connectivity as part of performance interpretation.

For remote spot workers:

* Do not stop at `k3s_server_url` and `k3s_token`.
* Include `trusted_cluster_cidrs` when required.
* If using Tailscale bootstrap, ensure both worker and control-plane networking assumptions match.
* Avoid mixed public/private networking assumptions for flannel and cross-node pod traffic.

## Debugging Defaults

For flashsale service debugging, use port-forwarding when appropriate:

```bash
kubectl port-forward -n flashsales svc/flashsales-user-service 8001:8001
kubectl port-forward -n flashsales svc/flashsales-product-service 8002:8002
kubectl port-forward -n flashsales svc/flashsales-order-service 8003:8003
```

For performance/debugging issues, investigate in this order:

1. Recent code path change.
2. Failing workflow or test gate.
3. Service logs and HTTP status distribution.
4. p95/p99 latency.
5. DB lock contention and transaction path.
6. CPU throttling and missing resource requests.
7. Readiness/liveness failures.
8. Queue/backlog behavior if async workers are involved.
9. Redis/RabbitMQ only after the bottleneck is identified.
10. More pods/spot workers only after confirming the service is horizontally scalable.

## Documentation Rules

When changing architecture or behavior, update the relevant doc:

* `flashsale/docs/flashsales.md`
* `flashsale/docs/flashsales-harness-engineering.md`
* `flashsale/docs/adrs/`
* `docs/operations.md`
* `docs/infrastructure.md`
* related Terraform module README files

If behavior changes the order/inventory lifecycle, add or update an ADR.

## Pull Request Expectations

A good PR should include:

* concise summary of the change.
* files or services touched.
* validation commands run.
* known risks.
* whether the change affects correctness, latency, deploy, or infrastructure.
* screenshots or Grafana panel notes if the change affects observability.

Do not claim performance improvement unless supported by a test run or metric.
Do not claim correctness improvement unless the consistency harness or equivalent validation was run.



## Change discipline

Before editing:
- Run `git status --short`.
- If working tree is not clean, stop and ask before modifying.

During work:
- Prefer minimal diffs.
- Do not create broad refactors while fixing a specific bug.
- Do not modify unrelated files.

Failure handling:
- If the same test/build fails twice after two different fixes, stop.
- Do not keep adding fallback code.
- Explain the suspected root cause and propose a rollback.
- Revert only the files changed in this session unless explicitly told otherwise.

Git safety:
- Before large edits, create a checkpoint commit or stash.
- Never run `git reset --hard` unless explicitly instructed.
- Never revert files that were dirty before the session started.
