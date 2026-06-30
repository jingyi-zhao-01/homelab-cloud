import { randomUUID, timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const port = Number.parseInt(process.env.PORT ?? "8080", 10);
const bindHost = process.env.HOST ?? "0.0.0.0";

function getRequiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }

  return value;
}

const sharedSecret = getRequiredEnv("MCP_SHARED_SECRET");

function sendJson(res: ServerResponse, statusCode: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(statusCode, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload),
    "cache-control": "no-store"
  });
  res.end(payload);
}

function unauthorized(res: ServerResponse): void {
  res.writeHead(401, {
    "www-authenticate": 'Bearer realm="chatgpt-mcp-hello"',
    "content-type": "application/json"
  });
  res.end(JSON.stringify({ error: "unauthorized" }));
}

function constantTimeMatch(actual: string, expected: string): boolean {
  const actualBuffer = Buffer.from(actual);
  const expectedBuffer = Buffer.from(expected);

  if (actualBuffer.length !== expectedBuffer.length) {
    return false;
  }

  return timingSafeEqual(actualBuffer, expectedBuffer);
}

function isAuthorized(req: IncomingMessage): boolean {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    return false;
  }

  return constantTimeMatch(authHeader.slice("Bearer ".length), sharedSecret);
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];

  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  if (chunks.length === 0) {
    return undefined;
  }

  const raw = Buffer.concat(chunks).toString("utf8");
  return JSON.parse(raw);
}

function createMcpServer(): McpServer {
  const server = new McpServer(
    {
      name: "chatgpt-mcp-hello",
      version: "0.1.0"
    },
    {
      capabilities: {
        tools: {}
      }
    }
  );

  server.registerTool(
    "hello_world",
    {
      title: "Hello World",
      description: "Return a simple greeting so ChatGPT can verify tool discovery and execution.",
      inputSchema: {
        name: z.string().trim().min(1).max(80).optional()
      }
    },
    async ({ name }) => {
      const target = name ?? "world";

      return {
        content: [
          {
            type: "text",
            text: `Hello, ${target}!`
          }
        ],
        structuredContent: {
          greeting: `Hello, ${target}!`,
          requestId: randomUUID()
        }
      };
    }
  );

  return server;
}

async function handleMcpRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  if (!isAuthorized(req)) {
    unauthorized(res);
    return;
  }

  if (req.method !== "POST") {
    sendJson(res, 405, {
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Method not allowed."
      },
      id: null
    });
    return;
  }

  const server = createMcpServer();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined
  });

  try {
    const parsedBody = await readBody(req);
    await server.connect(transport);
    await transport.handleRequest(req, res, parsedBody);
  } catch (error) {
    console.error("Failed to handle MCP request", error);
    if (!res.headersSent) {
      sendJson(res, 500, {
        jsonrpc: "2.0",
        error: {
          code: -32603,
          message: "Internal server error"
        },
        id: null
      });
    }
  } finally {
    await transport.close();
    await server.close();
  }
}

const httpServer = createServer(async (req, res) => {
  try {
    if (!req.url) {
      sendJson(res, 404, { error: "not_found" });
      return;
    }

    if (req.url === "/healthz" && req.method === "GET") {
      sendJson(res, 200, { ok: true });
      return;
    }

    if (req.url === "/mcp") {
      await handleMcpRequest(req, res);
      return;
    }

    sendJson(res, 404, { error: "not_found" });
  } catch (error) {
    console.error("Unhandled request failure", error);
    if (!res.headersSent) {
      sendJson(res, 500, { error: "internal_error" });
    }
  }
});

httpServer.listen(port, bindHost, () => {
  console.log(`chatgpt-mcp-hello listening on http://${bindHost}:${port}`);
});
