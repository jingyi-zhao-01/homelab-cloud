# LeetCode Intelligence Workload

LeetCode intelligence is a continuously running HTTP API workload for prompt dispatch, answer scoring, and focus recommendations.

## Runtime Contract

| Item | Value |
|---|---|
| Chart path | `charts/leetcode-intelligence` |
| Namespace | `leetcode-intelligence` |
| Container image | `ghcr.io/jingyi-zhao-01/leetcode-intelligence-service` |
| Service port | `8030` |
| Health endpoint | `GET /health` |

## Secret Wiring

The chart uses External Secrets Operator to read runtime secrets from AWS SSM Parameter Store.

| SSM path | Injected as |
|---|---|
| `/leetcode-intelligence/prod/DATABASE_URL` | `DATABASE_URL` |
| `/leetcode-intelligence/prod/OPEN_ROUTER_API_KEY` | `OPEN_ROUTER_API_KEY` |
| `/leetcode-intelligence/prod/API_KEY` | `API_KEY` |
| `/leetcode-intelligence/prod/DISCORD_BOT_TOKEN` | `DISCORD_BOT_TOKEN` |
| `/leetcode-intelligence/prod/PROMPT_DISCORD_CHANNEL_ID` | `PROMPT_DISCORD_CHANNEL_ID` |
| `/leetcode-intelligence/prod/RECOMMEND_DISCORD_CHANNEL_ID` | `RECOMMEND_DISCORD_CHANNEL_ID` |

## Config Defaults

The chart sets non-secret env defaults in `values.yaml`:

- `MODEL=openai/gpt-4o-mini`
- `INTELLIGENCE_PROMPT_CRON=0 9 * * *`
- `INTELLIGENCE_RECOMMEND_CRON=0 20 * * *`
- `INTELLIGENCE_RECOMMEND_TOP_K=5`
- `INTELLIGENCE_RECOMMEND_LOOKBACK_DAYS=30`

## Deploy

```bash
kubectl create namespace leetcode-intelligence --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install leetcode-intelligence charts/leetcode-intelligence -n leetcode-intelligence --set externalSecrets.enabled=true
```

## Related Pages

- [Repository overview](overview.md)
- [Operations and tooling](operations.md)

Back to [README](../README.md).
