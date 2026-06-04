# Observability Agent

This directory contains the observability agent for the Flashsales platform.

## Overview

The observability agent is an OpenHands SDK-based constant worker that:

- **Monitors GitHub Actions workflows** for perf test failures
- **Uses Grafana MCP** to analyze issues when tests fail
- **Creates PRs** to fix code issues (if within codebase)
- **Points out external integrations** that are not in the codebase

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Observability Agent (OpenHands SDK)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ GitHub API   │  │  SSM Store   │  │  Grafana MCP │  │  LLM      │ │
│  │ (monitors    │  │ (Grafana    │  │ (queries    │  │ (reasoning│ │
│  │  failures)   │  │  token)      │  │  metrics)    │  │  /PR gen) │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  GitHub PRs     │
                    └─────────────────┘
```

## Features

1. **Continuous Monitoring**: Runs as a constant worker on the control plane node
2. **Grafana Integration**: Uses Grafana MCP to query metrics when perf tests fail
3. **Automated Analysis**: Analyzes failures and determines root cause
4. **PR Creation**: Creates PRs to fix code issues (if within codebase)
5. **External Issue Detection**: Points out external integration issues

## Files

- `observability_agent.py` - Main agent script
- `test_observability_agent.py` - Test suite (requires external dependencies)
- `test_observability_agent_simple.py` - Simple test suite (self-contained)

## Requirements

- Python 3.11+
- boto3 (for AWS SSM)
- requests (for HTTP APIs)
- openhands-sdk (optional, for enhanced agent reasoning)

## Configuration

### Environment Variables

The agent requires these environment variables. **None have hardcoded defaults for critical values.**

#### Required (agent exits with a fatal log line if any are missing)

| Variable | Example | Source |
|---|---|---|
| `GITHUB_OWNER` | `jzhao62` | GitHub Actions context / k8s env |
| `GITHUB_REPO` | `homelab-cloud` | GitHub Actions context / k8s env |
| `GITHUB_TOKEN` | `ghp_...` | GitHub Actions `secrets.GITHUB_TOKEN` / k8s Secret |
| `AWS_REGION` | `us-west-1` | Repository var |
| `GRAFANA_URL` | `https://grafana.example.com` | Repository var |

#### SSM paths (configurable – agent fetches secrets at runtime via boto3)

| Variable | Default | SSM parameter |
|---|---|---|
| `GRAFANA_TOKEN_SSM_PATH` | `/codex/grafana-service-account-token` | Grafana service-account token |
| `LLM_API_KEY_SSM_PATH` | `/flashsales/prod/llm-api-key` | OpenRouter API key |

#### LLM / OpenRouter (non-secret – stored as repository vars)

| Variable | Example | Notes |
|---|---|---|
| `LLM_MODEL` | `openai/gpt-4o` | OpenRouter model slug |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter base URL |

#### Agent behaviour

| Variable | Default | Notes |
|---|---|---|
| `WORKFLOW_NAME` | `flashsales-perf-concurrency-suite.yml` | Workflow to monitor |
| `CHECK_INTERVAL` | `300` | Seconds between polls |
| `LOOKBACK_HOURS` | `12` | Lookback window for failures |
| `LOG_LEVEL` | `INFO` | Python log level |
| `LOG_FORMAT` | `json` | `json` for structured, `text` for human-readable |

### AWS SSM Parameters

Parameters that must be provisioned in AWS SSM before deploying the agent:

| SSM path | Terraform variable | Managed by | Notes |
|---|---|---|---|
| `/codex/grafana-service-account-token` | `grafana_service_account_token` | `terraform/ssm` | Grafana service-account token (also available at `/${ssm_path_prefix}/grafana-service-account-token`) |
| `/${ssm_path_prefix}/llm-api-key` | `llm_api_key` | `terraform/ssm` | OpenRouter API key (e.g. from https://openrouter.ai/keys) |
| `/${ssm_path_prefix}/DATABASE_URL` | `database_url` | `terraform/ssm` | Neon connection string (existing) |
| `/${ssm_path_prefix}/POSTGRES_USER` | `postgres_user` | `terraform/ssm` | Neon user (existing) |
| `/${ssm_path_prefix}/POSTGRES_PASSWORD` | `postgres_password` | `terraform/ssm` | Neon password (existing) |
| `/${ssm_path_prefix}/POSTGRES_DB` | `postgres_db` | `terraform/ssm` | Neon database (existing) |

Parameters managed as **GitHub repository variables** (non-secret):
`GRAFANA_URL`, `AWS_REGION`, `SSM_PATH_PREFIX`, `LLM_MODEL`, `LLM_BASE_URL`, `CHECK_INTERVAL`, `LOOKBACK_HOURS`, `LOG_LEVEL`, `LOG_FORMAT`, `CONTINUOUS_RUN_DURATION`

Parameters managed as **GitHub environment secrets**:
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (SSM access), `GITHUB_TOKEN` (auto-injected)

To provision:
```bash
terraform -chdir=terraform/ssm apply \
  -var grafana_service_account_token="<token>" \
  -var llm_api_key="<openrouter-key>" \
  -var ssm_path_prefix="flashsales/prod" \
  -var aws_region="us-west-1" \
  # ... other required vars (postgres_user, postgres_password, etc.)
```

### Helm Chart

Enable the observability agent in `charts/flashsales/values.yaml`:

```yaml
observabilityAgent:
  enabled: true
  image:
    repository: python
    tag: "3.11-slim"
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"
  aws:
    region: "us-west-1"
  ssm:
    grafanaTokenPath: "/codex/grafana-service-account-token"
    llmApiKeyPath: "/flashsales/prod/llm-api-key"
  grafana:
    url: "https://your-grafana.example.com"
  github:
    owner: "your-org"
    repo: "your-repo"
    githubToken: ""   # Set via --set or sealed secret; required for k8s mode
  llm:
    model: "openai/gpt-4o"
    baseUrl: "https://openrouter.ai/api/v1"
  workflowName: "flashsales-perf-concurrency-suite.yml"
  checkInterval: 300
  logLevel: "INFO"
  logFormat: "json"
```

## Usage

### Run Manually

```bash
export GITHUB_OWNER="jzhao62"
export GITHUB_REPO="homelab-cloud"
export GITHUB_TOKEN="$(gh auth token)"     # or a PAT
export AWS_REGION="us-west-1"
export GRAFANA_URL="https://grafana.example.com"
export LLM_MODEL="openai/gpt-4o"           # optional
export LLM_BASE_URL="https://openrouter.ai/api/v1"  # optional
export GRAFANA_TOKEN_SSM_PATH="/codex/grafana-service-account-token"
export LLM_API_KEY_SSM_PATH="/flashsales/prod/llm-api-key"
export LOG_FORMAT="text"                    # readable logs for local runs

python flashsale/perf/python/observability_agent.py
```

### Run in GitHub Actions

The `observability-agent.yml` workflow in `.github/workflows/` can be triggered:

**Single Run Mode**:
```bash
gh workflow run observability-agent.yml -f mode=single-run
```

**Continuous Mode** (daemon):
```bash
gh workflow run observability-agent.yml -f mode=continuous
```

### As Kubernetes Deployment

Deploy using Helm with the observability agent enabled:

```bash
helm upgrade -n flashsales flashsales ./charts/flashsales \
  -f ./charts/flashsales/values.yaml \
  --set observabilityAgent.enabled=true
```

## How It Works

1. **Monitoring**: The agent periodically checks GitHub Actions for failed workflow runs
2. **Analysis**: When a perf test fails, it analyzes the failure:
   - Queries Grafana for metrics (latency, error rates, throughput)
   - Uses LLM (if available) to reason about the root cause
   - Determines if issue is code-related or external
3. **Remediation**:
   - For code issues: Creates a PR with suggested fixes
   - For external issues: Creates a report with findings and recommendations

## Testing

Run the simple test suite:

```bash
cd flashsale/perf/python
python3 test_observability_agent_simple.py
```

## External Dependencies

The agent requires access to:

- **AWS SSM API**: For reading secrets (SSM paths: `/{SSM_PATH_PREFIX}/*`)
- **Grafana API**: For metrics queries (read access to dashboards)
- **GitHub API**: For workflow and PR operations (workflow, repo scopes)
- **LLM API**: For agent reasoning (OpenAI or compatible endpoint)

## Monitoring

### Check Agent Logs (Kubernetes)

```bash
kubectl logs -n flashsales \
  -l app.kubernetes.io/component=observability-agent \
  -f
```

### Monitor Workflow Runs

```bash
gh run list --limit 10 --workflow observability-agent.yml
```

## Troubleshooting

### Agent cannot access SSM
- Verify AWS IAM permissions
- Check SSM_PATH_PREFIX matches your configuration
- Ensure the Grafana token parameter exists in SSM

### Agent cannot query Grafana
- Verify GRAFANA_URL is correct
- Check GRAFANA_TOKEN has necessary permissions
- Ensure Grafana is accessible from the agent's network

### Agent cannot create PRs
- Verify GITHUB_TOKEN has PR creation permissions
- Check repository permissions (write access to PRs)

### Agent not starting (OpenHands SDK)
- Install OpenHands SDK: `pip install openhands-sdk`
- Or use the basic Python implementation (will work without OpenHands)

## Kubernetes RBAC

The agent requires the following RBAC permissions:

```yaml
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list"]
  - apiGroups: ["ssm"]
    resources: ["parameters"]
    verbs: ["get"]
```

## Security

- All secrets are stored in AWS SSM
- Grafana token is never logged
- GitHub token is passed securely via workflow environment
- Agent runs as non-root in Kubernetes

## Related

- [Operations and Tooling](../../docs/operations.md)
- [Flashsales Workload](../../flashsale/docs/flashsales.md)
- [Flashsales Grafana Dashboards](../../terraform/flashsale-grafana-dashboards/README.md)
- [Infrastructure](../../docs/infrastructure.md)
