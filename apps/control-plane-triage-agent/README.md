# control-plane-triage-agent

Long-running control-plane agent that watches configured GitHub Actions workflows, gathers failure context, requires OpenHands for diagnosis and operator chat, and posts the result to Discord.

## What it does

- polls GitHub Actions runs for configured repositories
- detects newly failed or cancelled runs
- downloads run logs and extracts high-signal failure snippets
- collects namespace-level Kubernetes diagnostics for the mapped workload
- runs an OpenHands SDK conversation over the failure bundle
- posts a compact incident summary to Discord

## Required secrets

Provision these into AWS SSM under `/control-plane-triage-agent/prod`:

- `GITHUB_TOKEN`
- `OPENHANDS_LLM_API_KEY`

## Core config

Important defaults:

- `OPENHANDS_ENABLED=true`
- `OPENHANDS_MODEL=openrouter/qwen/qwen3-coder-next`

The model name must include an explicit provider prefix such as `openrouter/...`.

`WATCH_TARGETS_JSON` is a JSON array.

If `workflow_names` and `workflow_ids` are omitted for a target, the agent will
watch all workflows in that repository that match the configured branch and
lookback window.

Example:

```json
[
  {
    "repository": "jingyi-zhao-01/homelab-cloud",
    "namespace": "flashsale",
    "branch": "main"
  },
  {
    "repository": "jingyi-zhao-01/homelab-cloud",
    "namespace": "strategy-tester",
    "branch": "main"
  },
  {
    "repository": "jingyi-zhao-01/homelab-cloud",
    "namespace": "leetcode-intelligence",
    "branch": "main"
  }
]
```

## Retention policy

The agent keeps disk usage bounded by pruning old incident workspaces and trimming long Discord history files.

Defaults:

- `INCIDENT_RETENTION_MAX_COUNT=25`
- `INCIDENT_RETENTION_MAX_AGE_DAYS=7`
- `OPERATOR_HISTORY_MAX_BYTES=131072`

Behavior:

- incident workspaces are stored under `STATE_DIR/incident-*`
- only the newest incident workspaces within the age window are kept
- `discord-operator-chat/*/HISTORY.md` is truncated to the latest bytes budget

## Image versioning

Deployments publish and use both:

- `latest`
- a commit-specific image tag equal to the full Git SHA

The Helm release deploys the commit-specific tag, and the Deployment/Pod
annotations also record:

- `control-plane-triage-agent/image-tag`
- `control-plane-triage-agent/git-sha`

This makes it easy to inspect exactly which image version is running with
`kubectl describe pod` or `kubectl get deployment -o yaml`.
