# AGENT.md

## Purpose

This repository is the control plane for a shared homelab k3s environment. It owns deploy orchestration, Helm release definitions, Terraform-backed resource provisioning, workflow automation, and platform documentation.

Treat this repo as the place where workloads are wired together, not the place where every workload's business logic should be re-explained.

## Scope Map

Start from the smallest relevant area instead of scanning the whole repo.

* `charts/`: Helm release definitions and workload runtime configuration.
* `.github/workflows/` and `.github/actions/`: CI/CD, deploy, post-deploy validation, and shared workflow logic.
* `.github/scripts/`: workflow-side orchestration helpers.
* `terraform/`: cloud resource provisioning, secret plumbing, networking, and worker capacity.
* `docs/`: platform-level documentation and operational runbooks.
* `wiki/`: root entrypoint to the repo wiki content.
* `application/flashsale/`: workload-owned app repo as a git submodule.
* `application/strategy-tester/`: workload-owned app repo as a git submodule.

## Working Model

This repo contains submodules, but they should not be treated as automatically in scope.

* Read submodule code only when the task clearly depends on workload internals.
* Prefer platform-layer changes first when the issue is about deploy behavior, env wiring, schedules, secrets, workflows, or cluster operations.
* If a change requires both platform and workload edits, inspect only the targeted workload submodule, not every submodule.
* Do not carry unrelated flashsale business logic into root-level decisions unless the current task explicitly depends on it.
* When entering a workload submodule, look for a local `AGENT.md` before inferring workload-specific rules.

## Source Of Truth

Use the closest source of truth for the task:

* repo behavior and operator entrypoints: [README.md](/home/jingyi/PycharmProjects/homelab-cloud/README.md)
* platform layout and conventions: [docs/overview.md](/home/jingyi/PycharmProjects/homelab-cloud/docs/overview.md)
* infrastructure provisioning: [docs/infrastructure.md](/home/jingyi/PycharmProjects/homelab-cloud/docs/infrastructure.md)
* workflow and runtime operations: [docs/operations.md](/home/jingyi/PycharmProjects/homelab-cloud/docs/operations.md)
* repo wiki and mirrored ADRs: [wiki/Home.md](/home/jingyi/PycharmProjects/homelab-cloud/wiki/Home.md)
* strategy-tester platform notes: [docs/strategy-tester.md](/home/jingyi/PycharmProjects/homelab-cloud/docs/strategy-tester.md)
* recruiter/resume evidence and story-bank content for MCP or resume tasks: [story-banks](/home/jingyi/jingyi-vault/story-banks)
* flashsale workload internals: [application/flashsale/AGENT.md](/home/jingyi/PycharmProjects/homelab-cloud/application/flashsale/AGENT.md)
* backend and infra-facing app code rules: [.codex/skills/home-cloud-rules/SKILL.md](/home/jingyi/PycharmProjects/homelab-cloud/.codex/skills/home-cloud-rules/SKILL.md)

Keep root guidance short. Push workload-specific business rules down into workload-owned docs.

## Story Bank Routing

For recruiter, resume, or interview-story tasks:

* Use the Obsidian story bank under [story-banks](/home/jingyi/jingyi-vault/story-banks) as the story-bank source of truth.
* Do not store story-bank content inside `apps/chatgpt-mcp-hello` unless the user explicitly asks for a checked-in snapshot.
* Do not go back to Google Drive for `walmart-story` unless the user explicitly asks to compare against the old source.
* Treat Google Drive `Resumes/` as the home for master resume docs and sendable artifacts, not as the story-bank source of truth.

## P3A Referral Routing

For 一亩三分地 / 1point3acres referral workflows:

* Use the local 1point3acres MCP as the default source for thread discovery and thread reading.
* Do not use generic web search to find or parse 1point3acres referral posts unless the user explicitly overrides this.
* Use external web search only after the thread is known, and only for the post's requested outside research such as job links, careers pages, or extra role details.

## Editing Rules

* Prefer minimal, focused diffs.
* Do not rename public workflow names, Helm values, Terraform variables, Kubernetes resource names, or Make targets unless the task requires it.
* Do not rewrite unrelated files while fixing a narrow issue.
* Preserve existing operator entrypoints when possible.
* If platform behavior changes, update the nearest relevant doc in `docs/`.
* If the change affects a durable workload decision or investigation trail, update `wiki/` as well.
* Treat submodules as externally owned repos by default and modify them only when the task explicitly targets them.

## Safety Rules

Before editing:

* Run `git status --short`.
* If the worktree is dirty, understand whether the target files are already modified before editing.
* Never revert user changes you did not make.

During work:

* Validate with the cheapest relevant check first.
* Prefer `helm template`, `helm lint`, `kubectl diff`, workflow YAML validation, or targeted compile/test commands before broader runs.
* For Terraform changes, prefer `terraform plan` or existing plan targets before any apply path.
* Do not expose secrets in docs, logs, commits, or values files unless the user explicitly asks and understands the risk.

Never do these without explicit approval:

* `terraform destroy`
* `helm uninstall`
* `kubectl delete`
* destructive database commands
* `git reset --hard`

## Debugging Order

For deploy or runtime issues, investigate in this order:

1. The smallest relevant chart, workflow, or script change.
2. Whether the wrong image tag, env var, secret, or path is wired.
3. Whether the workload code actually matches the deployed platform assumptions.
4. Runtime logs, Kubernetes events, and job/pod state.
5. Resource, networking, or infra-level constraints only after wiring and workload behavior are verified.

## Validation Defaults

Prefer checks that match the layer you changed:

* Helm: `helm template`, `helm lint`
* Workflows: YAML render/parse checks and targeted script compile checks
* Python helpers: `python3 -m py_compile` or targeted tests
* Terraform: formatting and plan-oriented validation

Do not claim deploy, correctness, or performance improvement unless you actually ran a relevant validation step or inspected live evidence.
