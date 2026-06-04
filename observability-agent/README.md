# Observability Agent

HTTP server deployed as a standalone Kubernetes Deployment in namespace `observability-agent`.

Receives `POST /analyze` payloads from GitHub Actions when a perf test workflow fails,
then autonomously scaffolds analysis and remediation.

## Architecture

```
GitHub Actions (perf suite fails)
  │
  ▼
observability-agent.yml (POST {run_id, run_name, run_url, conclusion})
  │
  ▼
Observability Agent (k8s Deployment, ns: observability-agent)
  │
  ├── SSM → Grafana token, LLM API key
  ├── Grafana API → metrics
  ├── GitHub API → job details, logs
  ├── OpenHands SDK → autonomous scaffold
  └── GitHub API → create PR
```

## Quick Start

```bash
# 1. Deploy the Helm chart
helm upgrade --install obs-agent ./charts/observability-agent \
  --namespace observability-agent --create-namespace \
  --set awsRegion="us-west-1" \
  --set grafanaUrl="https://grafana.example.com" \
  --set githubOwner="jzhao62" \
  --set githubRepo="homelab-cloud" \
  --set githubToken="ghp_..." \
  --set agentAuthToken="$(openssl rand -hex 32)"

# 2. Set GitHub repo variables
#    OBSERVABILITY_AGENT_URL = "https://obs-agent.your-domain.com"
#    OBSERVABILITY_AGENT_TOKEN = (same as agentAuthToken above)

# 3. Make sure SSM has:
#    /codex/grafana-service-account-token
#    /flashsales/prod/llm-api-key (optional – for OpenHands SDK)
```

## Configuration

| Env variable | Required | Source |
|---|---|---|
| `AGENT_AUTH_TOKEN` | Yes | k8s Secret (shared with GitHub Actions) |
| `GITHUB_OWNER` | Yes | k8s Deployment env |
| `GITHUB_REPO` | Yes | k8s Deployment env |
| `GITHUB_TOKEN` | Yes | k8s Secret |
| `AWS_REGION` | Yes | k8s Deployment env |
| `GRAFANA_URL` | Yes | k8s Deployment env |
| `GRAFANA_TOKEN_SSM_PATH` | No | Default: `/codex/grafana-service-account-token` |
| `LLM_API_KEY_SSM_PATH` | No | Default: `/flashsales/prod/llm-api-key` |
| `LLM_MODEL` | No | e.g. `openai/gpt-4o` |
| `LLM_BASE_URL` | No | e.g. `https://openrouter.ai/api/v1` |
| `LISTEN_PORT` | No | Default: `8080` |
| `LOG_LEVEL` | No | Default: `INFO` |
| `LOG_FORMAT` | No | Default: `json` |

## API

### POST /analyze

Triggered by GitHub Actions when a perf test fails.

**Headers:**
- `Content-Type: application/json`
- `X-Agent-Token: <shared-secret>`

**Body:**
```json
{
  "run_id": 12345,
  "run_name": "Flashsales Perf Concurrency Suite",
  "run_url": "https://github.com/org/repo/actions/runs/12345",
  "conclusion": "failure"
}
```

**Responses:**
- `202` — Accepted, analysis queued
- `400` — Missing `run_id` or invalid JSON
- `403` — Invalid/missing `X-Agent-Token`

### GET /health

Returns `{"status": "ok"}` with HTTP 200.

## Tests

```bash
cd observability-agent
python3 test_observability_agent.py
```

## Logs

The agent writes structured JSON to stdout. Key fields: `ts`, `level`, `logger`, `msg`, `exception`.

```bash
kubectl logs -n observability-agent \
  -l app.kubernetes.io/component=observability-agent -f
```

## File layout

- `observability-agent/observability_agent.py` — canonical agent source
- `observability-agent/test_observability_agent.py` — tests
- `charts/observability-agent/files/observability_agent.py` — Helm chart copy (kept in sync)
- `charts/observability-agent/` — Helm chart (Deployment, Service, Secret, ConfigMap, etc.)
