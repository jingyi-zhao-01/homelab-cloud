# ADR 0001: Expose A Minimal Remote MCP Server Through Kubernetes And Cloudflare Tunnel

- Status: Accepted
- Date: 2026-06-30

## Context

We wanted to prove one narrow thing end to end:

- ChatGPT can connect to a remote MCP server we control
- ChatGPT can discover tools from that server
- ChatGPT can call those tools over the public internet

The target environment is a homelab Kubernetes cluster fronted by a Cloudflare
domain. The intended user is a single operator, not a shared multi-tenant
product. That changes the bar for operational complexity:

- a simple manual recovery path is acceptable
- occasional re-authorization after restart is acceptable
- avoiding extra infrastructure is more valuable than HA purity

The first version only needs one tool, `hello_world`, to validate the full
chain.

## Decision

We will run a minimal Node/TypeScript MCP server in Kubernetes, expose it
through Cloudflare Tunnel, and use an in-process OAuth authorization server
implemented with the MCP TypeScript SDK.

We explicitly accept that:

- OAuth client registrations, authorization codes, and access tokens live only
  in memory
- a pod restart invalidates that in-memory OAuth state
- for a single-user setup, manual rolling restart and reconnect is an
  acceptable recovery mechanism

We explicitly do not add a database, Redis, external identity provider, or
multi-replica session coordination in this version.

## Architecture

The runtime path is:

1. ChatGPT reads MCP resource metadata from the public server URL
2. ChatGPT discovers the OAuth authorization server metadata
3. ChatGPT dynamically registers as an OAuth client
4. ChatGPT completes OAuth authorization code flow with PKCE
5. ChatGPT receives a bearer token from the in-process auth server
6. ChatGPT calls the public `/mcp` endpoint with that bearer token
7. Cloudflare edge receives the HTTPS request
8. Cloudflare Tunnel forwards the request to `cloudflared` in the cluster
9. `cloudflared` forwards to the in-cluster `chatgpt-mcp-hello` service
10. the Node app validates the bearer token and hands the request to the MCP
    transport
11. the MCP server exposes and executes the `hello_world` tool

The public request path is:

`ChatGPT -> Cloudflare DNS/edge -> Cloudflare Tunnel -> cloudflared pod -> Kubernetes Service -> chatgpt-mcp-hello pod`

## Cluster And Cloudflare Interaction

### Kubernetes responsibilities

Kubernetes runs two workloads:

- the `chatgpt-mcp-hello` application pod
- the `cloudflared` tunnel pod

Kubernetes also provides:

- a ClusterIP service for in-cluster routing to the app
- health checks on `/healthz`
- secret injection through External Secrets

The cluster does not terminate public TLS and does not expose an Ingress for
this service.

### Cloudflare responsibilities

Cloudflare provides:

- the public hostname
- edge TLS termination
- the tunnel control plane
- forwarding from the hostname to the running `cloudflared` connector

This keeps public ingress out of the cluster and avoids managing certificates
or ingress-controller policy for this experiment.

### Secret flow

AWS SSM Parameter Store is the source of truth for the tunnel token. External
Secrets syncs it into Kubernetes. The chart-level mapping lives in:

- `charts/chatgpt-mcp-hello/ssm-parameter-keys.yaml`

For this minimal OAuth version, no separate MCP bearer secret is required.

## ChatGPT Interaction

ChatGPT does not connect from the user's browser directly to the in-cluster
service. ChatGPT's backend connects to the public MCP URL.

That is why:

- Tailscale-only private access is not enough
- browser-local secrets are not enough
- `No Auth` plus a hidden static token is not enough

ChatGPT needs a public HTTPS endpoint and an auth mechanism it understands.
For custom remote MCP servers, the low-friction standards-compliant option is
OAuth.

## Why This Minimal Solution

We chose this design because it is the smallest thing that satisfies the real
constraints.

### 1. Public reachability was required

ChatGPT must be able to reach the server from OpenAI-controlled infrastructure.
That ruled out local-only or tailnet-only access patterns.

### 2. ChatGPT-compatible auth was required

Static bearer auth worked for manual `curl` validation but was not a good fit
for ChatGPT custom app setup. OAuth is what ChatGPT can negotiate cleanly.

### 3. Cloudflare Tunnel was cheaper than cluster ingress work

Cloudflare Tunnel gave us:

- a public hostname we already own
- no public load balancer requirement
- no ingress-controller work
- no certificate management work

For a single small MCP server, this is less moving parts than adding a new
public ingress path.

### 4. In-memory OAuth was enough for the current operator model

Persistent OAuth state would require extra infrastructure and code:

- persistent client storage
- persistent token/code storage
- token revocation semantics across restarts
- multi-pod coordination

That would be overkill for a single-user server whose main job is proving the
integration path.

The current user model tolerates:

- reconnecting after restart
- re-registering the client after restart
- manual rolling restart during maintenance

So we intentionally took the simpler version.

## Rejected Alternatives

### 1. Static bearer token only

Rejected because manual clients can use it, but ChatGPT custom remote MCP setup
does not naturally manage user-supplied static bearer credentials the way we
need.

### 2. Tailscale-only exposure

Rejected because ChatGPT backend traffic does not originate from the user's
device or tailnet.

### 3. Kubernetes Ingress with public exposure

Rejected for now because it adds certificate, ingress, and public entrypoint
management without improving the actual validation goal.

### 4. External OAuth provider or full identity layer

Rejected because it would add the most complexity while solving a problem we do
not yet have. The current use case is one operator and one simple MCP server.

### 5. Persistent auth state store

Rejected for now because it adds storage and lifecycle work for limited
benefit. Restart-driven state loss is acceptable in this single-user setup.

## Consequences

Benefits:

- minimal infrastructure surface
- public HTTPS access works through the existing Cloudflare domain
- ChatGPT can discover and call MCP tools through a standards-based auth flow
- no database or Redis dependency for the auth layer
- easy to reason about and easy to delete later

Tradeoffs:

- OAuth state disappears on pod restart
- the deployment is intentionally single-node and single-user friendly rather
  than highly available
- adding more than one app replica would require shared auth state or sticky
  routing
- operator reconnect/re-auth is part of the recovery story

## Operational Notes

This design is acceptable as long as these assumptions stay true:

- there is effectively one human operator
- reconnect after restart is low cost
- manual rolling restart is acceptable maintenance
- this server is validating a narrow MCP integration path, not acting as a
  general shared platform

If those assumptions change, the next likely upgrades are:

1. persist OAuth client and token state
2. support multi-replica deployment safely
3. decide whether to keep Cloudflare Tunnel or move to a standard ingress path
4. add a real login or external auth provider if multiple humans need access

## Related Files

- `apps/chatgpt-mcp-hello/src/index.ts`
- `apps/chatgpt-mcp-hello/package.json`
- `charts/chatgpt-mcp-hello/values.yaml`
- `charts/chatgpt-mcp-hello/templates/deployment.yaml`
- `charts/chatgpt-mcp-hello/templates/tunnel-deployment.yaml`
- `charts/chatgpt-mcp-hello/templates/service.yaml`
- `charts/chatgpt-mcp-hello/ssm-parameter-keys.yaml`
- `.github/workflows/deploy-chatgpt-mcp-hello.yml`
