# Strategy Tester Workload

Strategy tester is the scheduled ingestion workload. It is packaged as its own Helm chart in `charts/strategy-tester` and is driven by cron jobs rather than a continuously running API.

## Scheduled Jobs

| Job | Purpose | Schedule |
|---|---|---|
| `option-ingestor` | Pulls option data from Polygon | Daily at 21:00 EST, expressed as `0 2 * * *` UTC |
| `snapshot-ingestor` | Pulls portfolio snapshots | Daily at 23:00 EST, expressed as `0 4 * * *` UTC |

## Secrets

The chart uses External Secrets Operator to read from AWS SSM Parameter Store.

| SSM path | Injected as |
|---|---|
| `/strategy-tester/prod/DATABASE_URL` | `DATABASE_URL` |
| `/strategy-tester/prod/POLYGON_API_KEY` | `POLYGON_API_KEY` |

## Deploy

```bash
kubectl create namespace strategy-tester --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install strategy-tester charts/strategy-tester -n strategy-tester --set externalSecrets.enabled=true
```

## Related Pages

- [Repository overview](overview.md)
- [Operations and tooling](operations.md)

Back to [README](../README.md).
