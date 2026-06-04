# Flashsale Architecture

This page is the entry point for the flashsale architecture diagrams. These diagrams stay at the application and domain level only: no Kubernetes layout, no Grafana provisioning, no deployment topology.

## Diagrams

### 1. C4 Container Diagram

- D2 source: [flashsale-c4-container.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-c4-container.d2)
- Rendered SVG: [flashsale-c4-container.svg](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-c4-container.svg)

Shows the core runtime containers and dependencies:

- client
- user-service
- order-service
- product-service
- order Postgres
- product Postgres
- order terminalization queue

### 2. Runtime Flow Diagram

- D2 source: [flashsale-runtime-order-flow.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-runtime-order-flow.d2)
- Rendered SVG: [flashsale-runtime-order-flow.svg](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-runtime-order-flow.svg)

Shows one order request end to end:

- synchronous validation and reservation
- order persistence
- queue enqueue
- async confirm / cancel worker path

### 3. State Machine Diagram

- D2 source: [flashsale-state-machines.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-state-machines.d2)
- Rendered SVG: [flashsale-state-machines.svg](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-state-machines.svg)

Shows three lifecycle models side by side:

- order state machine
- reservation state machine
- terminalization task state machine
