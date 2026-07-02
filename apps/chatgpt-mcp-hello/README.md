# chatgpt-mcp-hello

Remote MCP server exposed through Cloudflare Tunnel for ChatGPT.

## What It Does

This app is the public MCP entrypoint for the homelab setup.

Today it serves three roles:

- exposes a Streamable HTTP MCP endpoint at `/mcp`
- handles OAuth for ChatGPT-compatible remote MCP access
- aggregates local tools plus proxied upstream MCP tools

Current tool sources:

- local demo tool: `hello_world`
- optional Zhihu tools from `src/zhihu.ts`
- proxied Arch Linux tools from upstream `arch-mcp`

## arch-mcp Integration

`arch-mcp` is not reimplemented here.

Instead, `chatgpt-mcp-hello` starts the upstream Python MCP server as a child
process over `stdio`, then re-exposes its tools through this app's public HTTP
MCP server.

Why this shape:

- upstream `arch-mcp` recommends `stdio` as the primary transport
- we keep one public MCP endpoint for ChatGPT
- upstream updates stay cheap: bump the installed `arch-ops-server` version

Reference docs:

- upstream install page: <https://nxk.mintlify.app/arch-mcp/install>
- upstream repo: <https://github.com/nihalxkumar/arch-mcp>

Relevant code:

- bridge: [src/arch-mcp.ts](./src/arch-mcp.ts)
- MCP server registration: [src/index.ts](./src/index.ts)

## Runtime Knobs

Main environment variables:

- `PUBLIC_BASE_URL`: public HTTPS base URL for OAuth and MCP metadata
- `HOST`: bind host, usually `0.0.0.0`
- `PORT`: app port, usually `8080`
- `ARCH_MCP_ENABLED`: defaults to enabled; set to `false` to disable the bridge
- `ARCH_MCP_COMMAND`: child-process command for upstream arch-mcp
- `ZHIHU_API_KEY`: enables Zhihu tools when set

`ARCH_MCP_COMMAND` defaults to:

```text
arch-ops-server
```

In the container image we currently install:

```text
arch-ops-server==3.4.0
```

via a Python virtualenv in the Docker image, so startup does not depend on
`uvx` downloading packages at runtime.

## Local Dev

Install Node deps:

```bash
npm ci
```

Run tests:

```bash
npm test
```

Run locally:

```bash
PUBLIC_BASE_URL=http://localhost:8080 npm run dev
```

If you want the Arch bridge locally, make sure `arch-ops-server` is on `PATH`,
or point `ARCH_MCP_COMMAND` at a specific binary.

Example:

```bash
ARCH_MCP_COMMAND=/path/to/arch-ops-server PUBLIC_BASE_URL=http://localhost:8080 npm run dev
```

## Deployment Notes

Kubernetes and tunnel wiring live under:

- [../../charts/chatgpt-mcp-hello](../../charts/chatgpt-mcp-hello)

The current chart enables the Arch bridge by default in
[../../charts/chatgpt-mcp-hello/values.yaml](../../charts/chatgpt-mcp-hello/values.yaml).
