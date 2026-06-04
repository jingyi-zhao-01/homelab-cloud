# Flashsale Architecture

This page is the entry point for the flashsale workload architecture diagram.

## Diagram

- D2 source: [flashsale-architecture.d2](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-architecture.d2)
- Rendered SVG: [flashsale-architecture.svg](/home/jingyi/PycharmProjects/homelab-cloud/flashsale/docs/diagram/flashsale-architecture.svg)

## Notes

- The primary purchase path is `client -> ingress -> order-service -> product-service`.
- `confirm/cancel` is shown on the async path through the reservation terminalization outbox and worker.
- The diagram keeps edge, application, async, data, and observability concerns in separate planes for easier review.
- The current async-path Grafana dashboard provisioning lives in [terraform/flashsale-grafana-dashboards](../terraform/flashsale-grafana-dashboards/README.md).
- Its SQL panels expect a Grafana `PostgreSQL` datasource backed by Neon, and its log panels expect Loki.
