# Flashsale Architecture

This page is the entry point for the flashsale architecture diagrams. These diagrams stay at the application and domain level only: no Kubernetes layout, no Grafana provisioning, no deployment topology.

## Diagrams

### 1. C4 Container Diagram

Shows the core runtime containers and dependencies:

- client
- user-service
- order-service
- product-service
- order Postgres
- product Postgres
- order terminalization queue

![Flashsale C4 Container Diagram](./docs/diagram/flashsale-c4-container.svg)

Source: [flashsale-c4-container.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-c4-container.d2)

### 2. Runtime Flow Diagram

Shows one order request end to end:

- synchronous validation and reservation
- order persistence
- queue enqueue
- async confirm / cancel worker path

![Flashsale Runtime Order Flow](./docs/diagram/flashsale-runtime-order-flow.svg)

Source: [flashsale-runtime-order-flow.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-runtime-order-flow.d2)

### 3. State Machine Diagram

Shows three lifecycle models side by side:

- order state machine
- reservation state machine
- terminalization task state machine

![Flashsale State Machines](./docs/diagram/flashsale-state-machines.svg)

Source: [flashsale-state-machines.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-state-machines.d2)
