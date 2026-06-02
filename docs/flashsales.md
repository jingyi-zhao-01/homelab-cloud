# Flashsales Workload

Flashsales is the concurrency practice workload. It is composed of three FastAPI services in the `flashsale/` tree and a Helm chart in `charts/flashsales`.

## Source Of Truth

Use this repo as the source of truth for flashsales status.

- For workload shape, deploy steps, and entry points, use this page.
- For current harness interpretation, known risks, and perf status, use [Flashsales harness engineering](flashsales-harness-engineering.md).

## Services

| Service | Responsibility |
|---|---|
| `user-service` | User persistence and lookup |
| `product-service` | Product catalog and stock management |
| `order-service` | Order creation, user validation, and stock reservation |

The workload also includes self-hosted PostgreSQL, Redis, and RabbitMQ in the chart.

## Deploy to VPS

```bash
kubectl create namespace flashsales --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install flashsales charts/flashsales -n flashsales
```

If you prefer the repo-managed workflow, use:

```bash
make deploy KUBECONFIG_PATH=$HOME/.kube/config
```

This workload is deployed to the VPS-backed k3s cluster, not to a local-only environment.

## Verification

```bash
./scripts/e2e-smoke.sh
```

The smoke test checks that the business services and supporting stateful components are running and reports success with `E2E PASS`.

For correctness gates:

- `flashsales-deploy-pre.yml` contains the pre-deploy unit gates
- `flashsales-deploy-pre.yml` also contains the pre-deploy Docker Compose integration gate based on `flashsale/docker-compose.yaml`
- `flashsales-deploy-pre.yml` calls the reusable runtime consistency harness in `flashsales-consistency.yml`
- `flashsales-deploy.yml` runs only after `flashsales-deploy-pre.yml` succeeds and performs the default k3s deploy
- `flashsales-deploy-post.yml` runs only after `flashsales-deploy.yml` succeeds and calls the reusable perf suite in `flashsales-perf-concurrency-suite.yml`
- the pre-deploy gate now covers lifecycle, out-of-stock, duplicate-order, duplicate-webhook, timeout-race, DB migration compatibility, and API contract compatibility

The current inventory flow uses an explicit reservation lifecycle:

- `reserve`
- `confirm`
- `cancel`
- `expire`

The current order flow also uses explicit order states in `order-service`:

- `pending`
- `confirmed`
- `failed`
- `expired`

Order requests now also carry:

- optional `idempotency_key`
- internal default-success `payment_status`
- pending-order timeout cleanup via `/admin/expire-orders`

## Debugging

```bash
kubectl port-forward -n flashsales svc/flashsales-user-service 8001:8001
kubectl port-forward -n flashsales svc/flashsales-product-service 8002:8002
kubectl port-forward -n flashsales svc/flashsales-order-service 8003:8003
```

Once forwarded, you can create users, products, and orders with the workload APIs.

## Related Pages

- [Flashsales harness engineering](flashsales-harness-engineering.md)
- [Repository overview](overview.md)
- [Operations and tooling](operations.md)

Back to [README](../README.md).
