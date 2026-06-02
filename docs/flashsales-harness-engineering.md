# Flashsales Harness Engineering

This page is the repository-level source of truth for the current flashsales workload behavior, known risks, and the performance harness interpretation.

Snapshot date: June 2, 2026.

## Intent

The flashsales workload exists to practice concurrency behavior on a live multi-service stack, not just to prove that the APIs return `201`.

The harness engineering goal is:

- keep correctness ahead of throughput
- document what the perf suite really measures
- record confirmed risks in the repo instead of leaving them in chat history
- make future changes compare against one written baseline

## Scope

This record covers:0.01

- `flashsale/user-service`
- `flashsale/product-service`
- `flashsale/order-service`
- `charts/flashsales`
- `perf/concurrency-test.js`
- `perf/loadtest-k6.sh`
- `perf/CONCURRENCY_TEST_PLAN.md`

## Current Architecture Summary

| Component | Current role | Notes for harness interpretation |
|---|---|---|
| `user-service` | User persistence and lookup | Order creation synchronously depends on it |
| `product-service` | Product read, reservation lifecycle, and stock management | Reservation state machine now owns `reserve/confirm/cancel/expire` |
| `order-service` | User validation, reserve orchestration, and order persistence | Confirms or cancels reservations after persistence outcome |
| `charts/flashsales` | Deployment source of truth | Ingress and HPA behavior directly affect perf conclusions |
| `perf/concurrency-test.js` | Main concurrency harness | Measures business outcomes and latency, but has correctness blind spots |

## Confirmed Findings

### 1. Inventory can be consumed without a persisted order

`order-service` currently reserves stock before persisting the order and does not compensate if a later step fails.

Implication:

- stock can decrease even when no order row is written
- the system can fail correctness without overselling
- current teardown checks do not catch this class of bug

Primary code path:

- `flashsale/order-service/app/service.py`

### 2. Public admin endpoints are part of the deployed surface

The workload exposes `/admin/reset` on all three services and `/admin/seed` on `product-service`, while the chart ingress forwards all paths for the public hosts.

Implication:

- anyone who can reach the service hosts can potentially reset workload state
- the current perf harness depends on that exposure
- the deployed environment behaves like an open test system, not a protected production-like service

Primary files:

- `flashsale/user-service/app/main.py`
- `flashsale/product-service/app/main.py`
- `flashsale/order-service/app/main.py`
- `charts/flashsales/templates/ingress.yaml`

### 3. Startup failures can be hidden behind healthy probes

Each service swallows startup initialization exceptions and still serves `/health` as `ok`. Kubernetes readiness and liveness currently rely on that endpoint.

Implication:

- pods can be marked healthy while DB init already failed
- perf runs may include broken instances that still receive traffic
- latency and error rates can look like runtime instability when the actual issue is startup masking

Primary files:

- `flashsale/user-service/app/main.py`
- `flashsale/product-service/app/main.py`
- `flashsale/order-service/app/main.py`

### 4. The hotspot profile does not measure sustained contention well

The `hotspot` profile in `perf/concurrency-test.js` uses one product with `initialStock=1` while driving `100 TPS` for three minutes.

Implication:

- after the first successful reservation, most requests become fast business rejection
- the profile mostly measures the post-sellout path
- it is not a trustworthy benchmark for comparing optimistic and pessimistic lock behavior under sustained contention

Primary files:

- `perf/concurrency-test.js`
- `perf/CONCURRENCY_TEST_PLAN.md`

### 5. Order-service HPA is unlikely to scale meaningfully as configured

The chart enables CPU-based HPA for `order-service`, but the default values only set a CPU limit and omit a CPU request.

Implication:

- CPU utilization based scaling may not behave as intended
- perf conclusions about scaling headroom are not reliable until requests are explicit

Primary files:

- `charts/flashsales/values.yaml`
- `charts/flashsales/templates/order-deployment.yaml`
- `charts/flashsales/templates/order-hpa.yaml`

### 6. The current correctness check can miss inventory leakage

The teardown logic only sums persisted order quantities and checks for oversell against initial stock.

Implication:

- it can detect "sold more than initial stock"
- it cannot detect "reserved stock but failed to persist order"
- a run can pass while inventory and orders are already inconsistent

Primary files:

- `perf/concurrency-test.js`

## What The Harness Currently Proves

Today the harness is strong enough to tell us:

- whether the basic order path stays up under configured arrival rates
- whether 5xx rates stay within the configured budget
- whether oversell appears in the persisted order records
- whether one lock mode looks slower than another in broad latency terms

Today the harness does not prove:

- that stock and persisted orders stay fully reconciled
- that the deployed environment is safe to expose publicly
- that HPA-driven scaling behavior is representative
- that the hotspot profile reflects steady-state contention after the first sellout event

## Runtime Consistency Harness

The repository now includes a dedicated consistency lane for the public k3s lifecycle:

- unit gate workflow: `.github/workflows/flashsales-deploy.yml`
- integration gate workflow: `.github/workflows/flashsales-consistency.yml`
- runtime script: `perf/consistency_harness.py`
- cluster component: optional `dbProxy` in `charts/flashsales`

The two gates have different roles:

- unit gate: runs before image build and deploy, using service-local unit tests for both the product reservation lifecycle and the order compensation path
- integration gate: runs after a successful deploy, using the public ingress path plus a cluster-side DB proxy fault injection lane

## Reservation Lifecycle

The current inventory model is now explicit about reservation phases:

- `reserve`: create a pending reservation and reduce immediately available stock
- `confirm`: finalize a reservation after order persistence succeeds
- `cancel`: release a reservation after downstream failure
- `expire`: reclaim stale pending reservations

Current ownership:

- `product-service` owns reservation state and stock transitions
- `order-service` orchestrates `reserve -> persist order -> confirm/cancel`
- `order-service` persists explicit order states: `pending -> confirmed` on success, and `pending -> failed` when post-reservation completion breaks

This lane keeps the current external request path intact:

- GitHub Actions runner
- public ingress hosts
- k3s workload
- Neon-backed database

The only injected change is inside the cluster: `order-service` can be switched to a `toxiproxy` hop before Neon. The harness waits until stock is visibly reserved, then disables the DB proxy to force an order persistence failure window.

The test is expected to fail while the inventory leak bug exists. The failure signature is:

- order request fails
- no order row is persisted
- product stock still decreases

## Working Interpretation Rules

Use these rules when reading flashsales perf results:

- Treat oversell checks as necessary but not sufficient.
- Treat `409` volume in hotspot runs as a business outcome, not proof of healthy contention handling.
- Do not call the system production-like while public admin endpoints remain reachable.
- Do not compare lock modes solely from hotspot results with `initialStock=1`.
- If a run shows surprising 5xx behavior, check startup masking before assuming lock-mode regression.

## Priority Backlog

### Correctness first

1. Add a compensation or reservation-finalization strategy so failed order persistence cannot silently leak stock.
2. Extend teardown verification to compare persisted orders against current product stock.

### Harness trustworthiness

1. Redesign the hotspot profile so it sustains contention instead of immediately exhausting stock.
2. Separate "business rejection under depletion" from "contention under finite but sufficient stock" as two distinct scenarios.
3. Keep the runtime consistency harness independent from the long-running k6 perf suite so correctness fails faster than throughput analysis.

### Deployment realism

1. Restrict or gate admin endpoints for deployed environments.
2. Make readiness reflect database initialization and critical dependency state.
3. Add CPU requests for `order-service` before relying on HPA conclusions.

## Suggested Verification After Future Changes

When changing flashsales correctness or perf semantics, verify at least:

```bash
./scripts/e2e-smoke.sh
make concurrency-smoke
make concurrency-baseline
make concurrency-hotspot
```

Then review:

- order count versus remaining stock
- `409` versus `5xx` ratio
- startup logs for swallowed initialization errors
- lock-mode-specific latency tails

For correctness-sensitive changes, also run:

```bash
python3 ./perf/consistency_harness.py
```

## Related Pages

- [Flashsales workload](flashsales.md)
- [Operations and tooling](operations.md)
- [Repository overview](overview.md)

Back to [README](../README.md).
