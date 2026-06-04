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

The agent requires the following environment variables:

```bash
# GitHub configuration
GITHUB_TOKEN=your-github-token
GITHUB_OWNER=jzhao62
GITHUB_REPO=homelab-cloud

# AWS SSM configuration
AWS_REGION=us-west-1
SSM_PATH_PREFIX=flashsales/prod

# Grafana configuration
GRAFANA_URL=https://your-grafana.example.com
GRAFANA_TOKEN=your-grafana-token

# OpenHands/LLM configuration (optional)
LLM_MODEL=gpt-4o
LLM_API_KEY=your-llm-api-key
LLM_BASE_URL=

# Agent configuration
CHECK_INTERVAL=300  # Check every 5 minutes
```

### AWS SSM Parameters

The agent reads the Grafana token from AWS SSM at:
```
/{SSM_PATH_PREFIX}/grafana-service-account-token
```

To provision this parameter:

```bash
terraform -chdir=terraform/ssm apply \
  -var grafana_service_account_token="your-grafana-token" \
  -var ssm_path_prefix="flashsales/prod"
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
    region: us-west-1
  ssm:
    pathPrefix: flashsales/prod
  grafana:
    url: "https://your-grafana.example.com"
  github:
    owner: your-org
    repo: your-repo
  llm:
    model: "gpt-4o"
  checkInterval: 300  # 5 minutes
```

## Usage

### Run Manually

```bash
export GITHUB_TOKEN="your-github-token"
export GRAFANA_TOKEN="your-grafana-token"
export GRAFANA_URL="https://your-grafana.example.com"
export SSM_PATH_PREFIX="flashsales/prod"

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
