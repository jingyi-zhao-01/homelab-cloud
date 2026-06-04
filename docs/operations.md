# Operations and Tooling

This page collects the operational commands and workflow details that used to be buried in the root README.

## CI/CD

| Workflow | Trigger | Scope |
| --- | --- | --- |
| `flashsales-deploy-pre.yml` | Pushes to `flashsale/**` or `charts/flashsales/**` | Flashsales pre-deploy gates |
| `flashsales-deploy.yml` | After a successful `flashsales-deploy-pre.yml` or manual dispatch | Flashsales deploy |
| `flashsales-deploy-post.yml` | After a successful `flashsales-deploy.yml` or manual dispatch | Flashsales post-deploy runtime consistency and perf |
| `deploy-strategy-tester.yml` | Pushes to `strategy-tester/**` or `charts/strategy-tester/**` | Strategy tester |
| `deploy-leetcode-intelligence.yml` | Pushes to `charts/leetcode-intelligence/**` | LeetCode intelligence |
| `flashsales-perf-concurrency-suite.yml` | Manual or reusable via `flashsales-deploy-post.yml` | Concurrency suite |
| `flashsales-loadtest-manual.yml` | Manual `workflow_dispatch` | Performance testing |
| `observability-agent.yml` | Perf test failure or manual | POSTs failed run to agent for autonomous analysis |
| `terraform-provision.yml` | Manual | Neon and SSM infrastructure provisioning |
| `terraform-k3s-spot-network.yml` | Manual | Low-cost VPC and public subnets for the spot worker |
| `terraform-k3s-spot-node.yml` | Manual | One self-healing AWS spot k3s worker |

The deploy workflows are independent, so changes to one workload should not trigger the other.

## Required Secrets

```text
KUBE_CONFIG_DATA
GHCR_PULL_USERNAME
GHCR_PULL_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
GRAFANA_AUTH
SSM_PATH_PREFIX
```

### Observability Agent

The observability agent is deployed in its own **independent namespace** (`observability-agent`).
It runs as an HTTP server that receives failed workflow run IDs from GitHub Actions
and autonomously scaffolds analysis and remediation.

**Architecture**: GitHub Actions → POST `/analyze` → Agent (k8s Deployment) → Grafana + LLM → PR / report.

### Quick start

```bash
# Deploy the agent to its own namespace
helm upgrade --install obs-agent ./charts/observability-agent \
  --namespace observability-agent --create-namespace \
  --set awsRegion="us-west-1" \
  --set grafanaUrl="https://grafana.example.com" \
  --set githubOwner="jzhao62" \
  --set githubRepo="homelab-cloud" \
  --set githubToken="ghp_..." \
  --set agentAuthToken="$(openssl rand -hex 32)"
```

### GitHub configuration

| Type | Name | Purpose |
|---|---|---|
| Repo variable | `OBSERVABILITY_AGENT_URL` | Agent endpoint URL (e.g. `https://obs-agent.example.com`) |
| Env secret | `OBSERVABILITY_AGENT_TOKEN` | Shared auth token (same as `agentAuthToken` Helm value) |

### AWS SSM parameters

| Path | Value |
|---|---|
| `/codex/grafana-service-account-token` | Grafana service-account token |
| `/flashsales/prod/llm-api-key` | OpenRouter API key |

Provision via Terraform: `terraform -chdir=terraform/ssm apply -var grafana_service_account_token=... -var llm_api_key=...`

### How it works

1. A perf test workflow fails → `observability-agent.yml` triggers.
2. The workflow extracts `run_id`, `run_name`, `run_url`, `conclusion` from the event.
3. It POSTs the JSON payload to `{OBSERVABILITY_AGENT_URL}/analyze` with header `X-Agent-Token`.
4. The agent (k8s deployment in namespace `observability-agent`) receives the request, validates the token, and enqueues it.
5. A background worker fetches job details, Grafana metrics, and workflow logs.
6. If OpenHands SDK + LLM are configured, the agent scaffolds an autonomous investigation and fix.
7. For code issues: a PR is created. For external issues: logged as error.

### Logs

```bash
kubectl logs -n observability-agent \
  -l app.kubernetes.io/component=observability-agent -f
```

Back to [README](../README.md).