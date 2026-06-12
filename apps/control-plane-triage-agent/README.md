# control-plane-triage-agent

Long-running control-plane agent that watches configured GitHub Actions workflows, gathers failure context, optionally asks OpenHands for a diagnosis, and posts the result to Discord.

## What it does

- polls GitHub Actions runs for configured repositories and workflow names/ids
- detects newly failed or cancelled runs
- downloads run logs and extracts high-signal failure snippets
- collects namespace-level Kubernetes diagnostics for the mapped workload
- optionally runs an OpenHands SDK conversation over the failure bundle
- posts a compact incident summary to Discord

## Required secrets

Provision these into AWS SSM under `/control-plane-triage-agent/prod`:

- `GITHUB_TOKEN`
- `DISCORD_WEBHOOK_URL`

Optional:

- `OPENHANDS_LLM_API_KEY`

## Core config

`WATCH_TARGETS_JSON` is a JSON array. Example:

```json
[
  {
    "repository": "jingyi-zhao-01/homelab-cloud",
    "workflow_names": ["Flashsales Deploy"],
    "namespace": "flashsale",
    "branch": "main"
  },
  {
    "repository": "jingyi-zhao-01/homelab-cloud",
    "workflow_names": ["Deploy Strategy Tester to strategy-tester Namespace"],
    "namespace": "strategy-tester",
    "branch": "main"
  },
  {
    "repository": "jingyi-zhao-01/homelab-cloud",
    "workflow_names": ["Deploy LeetCode Intelligence to leetcode-intelligence Namespace"],
    "namespace": "leetcode-intelligence",
    "branch": "main"
  }
]
```
