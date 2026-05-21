# Flashsales Workload

Flashsales is the concurrency practice workload. It is composed of three FastAPI services in the `flashsale/` tree and a Helm chart in `charts/flashsales`.

## Services

| Service | Responsibility |
|---|---|
| `user-service` | User persistence and lookup |
| `product-service` | Product catalog and stock management |
| `order-service` | Order creation, user validation, and stock reservation |

The workload also includes self-hosted PostgreSQL, Redis, and RabbitMQ in the chart.

## Local Deploy

```bash
kubectl create namespace flashsales --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install flashsales charts/flashsales -n flashsales
```

If you prefer the repo-managed workflow, use:

```bash
make deploy KUBECONFIG_PATH=$HOME/.kube/config
```

## Verification

```bash
./scripts/e2e-smoke.sh
```

The smoke test checks that the business services and supporting stateful components are running and reports success with `E2E PASS`.

## Debugging

```bash
kubectl port-forward -n flashsales svc/flashsales-user-service 8001:8001
kubectl port-forward -n flashsales svc/flashsales-product-service 8002:8002
kubectl port-forward -n flashsales svc/flashsales-order-service 8003:8003
```

Once forwarded, you can create users, products, and orders with the workload APIs.

## Related Pages

- [Repository overview](overview.md)
- [Operations and tooling](operations.md)

Back to [README](../README.md).
