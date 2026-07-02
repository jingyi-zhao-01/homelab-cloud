# homelab-cloud

Platform control plane for personal workload deploys, resource allocation, and runtime performance-test provisioning on a shared k3s environment.

## Why This Exists

I use AI to generate and iterate on a lot of service code, but the hard part is rarely just writing the code.

- local prototypes needs to be deployed efficiently and stable when interacting with external Apps (discord, chatgpt)
- infra and secrets provisioning should not be manually provisioned per prototype as it is really time consuming and put people down :(
- post-deploy quality lanes need real runtime capacity, not only local mocks
- security becomes more of a problem in OSS communities (Thank you Antropic!!!)

This repository is that shared platform layer. App repos can stay focused on vibe coding and service implementation, while `homelab-cloud` acts as the scheduler that:
- deploys workloads onto k3s
- allocates shared runtime resources such as cluster capacity, secrets, and databases
- provisions the runtime environment used by post-deploy quality lanes
- closes the loop with logs, metrics, and workflow feedback

## Platform Overview

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/4bd58d48-a03a-4bc0-aae9-c855d2af726a" />


This diagram is intentionally control-plane-first: it shows `homelab-cloud` as the orchestration layer that owns deploy execution, runtime resource allocation, and perf-test environment provisioning. The source lives in [docs/infra-overview.d2](docs/infra-overview.d2).


## Security + Network OverView
<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/5af7b538-4881-4716-a76b-09066b08be8e" />

- my infra is intentional hardened from scratch due to an increasing trend of vulnerabilities from public project being exploited, because every information is on your finger tip with AI. There was once i wonder if i could just use vercel instead of building everything natively, and after seeing it get compromised once i decided roll my sleeves and do it myself.
- Centralized secrets management auto provisioned in AWS parameter store, in case something goes sour can be immediately rotated.
- Dedicated *1 node* for public traffic ingress, behind cloudflare tunnel for better public traffic pattern and futhure hardening.
- tailscale for node to node communication and connecting personal devices (laptop + phone) in case something goes wrong every node is immediately accessible

## Resilience: 
- a sample perf test project (flashsale) is provisioned here for periodic performance test for resource and integrated middlewares 


## Per-Project Provisioning Flow

![per-project terraform provisioning flow](docs/per-project-provisioning.svg)

This D2 diagram is intentionally control-flow-first rather than runtime-topology-first: the key question is how one project-specific Terraform entrypoint provisions cloud resources, persists state, and then syncs runtime secrets into AWS SSM for Kubernetes consumption.

Read it left to right:

- each workload gets a project-owned Terraform entrypoint, such as `terraform/flashsale/`
- Terraform provisions only the cloud resources that belong to that project
- Terraform keeps desired state in the shared S3 backend, but writes runtime credentials into `AWS SSM Parameter Store`
- Kubernetes does not read Terraform state directly; `External Secrets Operator` reads the project SSM path and materializes a namespaced Secret
- the Helm release consumes that Secret at deploy time, so apps get `DATABASE_URL`, `REDIS_URL`, tokens, and other sensitive values without committing them to `values.yaml`

For flashsale specifically, the current aggregate stack is:

- `terraform/flashsale` provisions Neon, Upstash Redis, Grafana dashboards, and SSM parameters
- the default SSM path is `/flashsales/prod/*`
- the `charts/flashsales` chart can read those values through `ExternalSecret`

## What This Repo Schedules

| Control-plane responsibility | What it means here |
|---|---|
| Deploy orchestration | GitHub Actions drives Helm-based rollout into the shared k3s cluster |
| Resource allocation | Terraform and cluster config provision Neon, AWS SSM secrets, and spot-backed worker capacity |
| Runtime quality provisioning | Manual perf workflows prepare the live runtime needed by flashsale app-owned quality lanes |
| Feedback loop | Workflow logs, Discord notifications, Grafana, and docs feed runtime behavior back into the repo |

## Start Here

| Page | What it covers |
|---|---|
| [Repository overview](docs/overview.md) | High-level architecture, layout, and shared conventions |
| [Wiki](wiki/Home.md) | Mirrored investigations, ADRs, and workload notes with stable root-level paths |
| [Flashsales workload](application/flashsale/docs/flashsales.md) | App-owned release contract, k3s deploy path, and runtime perf cadence |
| [Flashsales harness engineering](application/flashsale/docs/flashsales-harness-engineering.md) | Current flashsales correctness risks, perf harness interpretation, and priority backlog |
| [Flashsale workload agent context](application/flashsale/AGENT.md) | Workload-specific architecture, validation order, and wiki/ADR mirroring rules |
| [Flashsales deploy pre](application/flashsale/.github/workflows/flashsales-deploy-pre.yml) | App-owned pre-deploy unit and Docker Compose integration gates |
| [Flashsales deploy](.github/workflows/flashsales-deploy.yml) | Platform-side deploy executor for the shared k3s runtime |
| [Flashsales perf test](.github/workflows/flashsales-loadtest-manual.yml) | Manual platform-side executor for the app-owned flashsale perf cadence |
| [Strategy tester workload](docs/strategy-tester.md) | Scheduled ingestion app for US option strategy tester, cron jobs, and secret wiring |
| [LeetCode intelligence workload](docs/leetcode-intelligence.md) | Continuous intelligence API service with Discord and LLM secret wiring |
| [Infrastructure](docs/infrastructure.md) | Terraform-backed resource provisioning for Neon, SSM, networking, and worker capacity |
| [Operations and tooling](docs/operations.md) | CI/CD, runtime gates, perf workflows, and operator commands |

For workflow-specific guidance, see [Operations and tooling](docs/operations.md).
