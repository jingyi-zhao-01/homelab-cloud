import { randomUUID } from "node:crypto";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { mcpAuthRouter } from "@modelcontextprotocol/sdk/server/auth/router.js";
import { requireBearerAuth } from "@modelcontextprotocol/sdk/server/auth/middleware/bearerAuth.js";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import type {
  OAuthClientInformationFull,
  OAuthClientMetadata,
  OAuthTokenRevocationRequest,
  OAuthTokens
} from "@modelcontextprotocol/sdk/shared/auth.js";
import type {
  AuthorizationParams,
  OAuthServerProvider
} from "@modelcontextprotocol/sdk/server/auth/provider.js";
import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import { z } from "zod";

import {
  buildHostFilter,
  extractZhihuHotListItems,
  extractZhihuSearchItems,
  inferQueryFromUrl,
  isZhihuHost,
  parseSharedUrl,
  zhihuGetJson
} from "./zhihu.js";

const port = Number.parseInt(process.env.PORT ?? "8080", 10);
const bindHost = process.env.HOST ?? "0.0.0.0";
const publicBaseUrl = getRequiredUrl("PUBLIC_BASE_URL");
const issuerUrl = new URL(publicBaseUrl.origin);
const mcpServerUrl = new URL("/mcp", publicBaseUrl);
const zhihuApiKey = process.env.ZHIHU_API_KEY;

function getRequiredUrl(name: string): URL {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }

  return new URL(value);
}

function getShortText(value: string, limit = 220): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length <= limit ? compact : `${compact.slice(0, limit - 1)}...`;
}

function createMcpServer(): McpServer {
  const server = new McpServer(
    {
      name: "chatgpt-mcp-hello",
      version: "0.2.0"
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

  if (zhihuApiKey) {
    server.registerTool(
      "zhihu_search",
      {
        title: "Zhihu Search",
        description: "Search content inside Zhihu.",
        inputSchema: {
          query: z.string().trim().min(2).max(100),
          count: z.number().int().min(1).max(10).optional()
        }
      },
      async ({ query, count }) => {
        const response = await zhihuGetJson(
          "/api/v1/content/zhihu_search",
          {
            Query: query,
            Count: count
          },
          zhihuApiKey
        );

        const items = extractZhihuSearchItems(response);
        const text = items.length === 0
          ? `No Zhihu results for "${query}".`
          : [
              `Zhihu results for "${query}":`,
              ...items.map((item, index) =>
                `${index + 1}. ${item.title} [${item.contentType}] by ${item.authorName} (${item.voteUpCount} votes)\n${item.url}\n${getShortText(item.contentText)}`
              )
            ].join("\n\n");

        return {
          content: [
            {
              type: "text",
              text
            }
          ],
          structuredContent: {
            query,
            count: items.length,
            items
          }
        };
      }
    );

    server.registerTool(
      "zhihu_global_search",
      {
        title: "Zhihu Global Search",
        description: "Search the web through Zhihu's global search API.",
        inputSchema: {
          query: z.string().trim().min(2).max(100),
          count: z.number().int().min(1).max(20).optional(),
          filter: z.string().trim().min(1).max(300).optional(),
          search_db: z.enum(["all", "realtime", "static"]).optional()
        }
      },
      async ({ query, count, filter, search_db }) => {
        const response = await zhihuGetJson(
          "/api/v1/content/global_search",
          {
            Query: query,
            Count: count,
            Filter: filter,
            SearchDB: search_db
          },
          zhihuApiKey
        );

        const items = extractZhihuSearchItems(response);
        const text = items.length === 0
          ? `No global results for "${query}".`
          : [
              `Global results for "${query}":`,
              ...items.map((item, index) =>
                `${index + 1}. ${item.title} [${item.contentType}] by ${item.authorName}\n${item.url}\n${getShortText(item.contentText)}`
              )
            ].join("\n\n");

        return {
          content: [
            {
              type: "text",
              text
            }
          ],
          structuredContent: {
            query,
            count: items.length,
            items
          }
        };
      }
    );

    server.registerTool(
      "zhihu_hot_list",
      {
        title: "Zhihu Hot List",
        description: "Get the current Zhihu hot list.",
        inputSchema: {
          limit: z.number().int().min(1).max(30).optional()
        }
      },
      async ({ limit }) => {
        const response = await zhihuGetJson(
          "/api/v1/content/hot_list",
          {
            Limit: limit
          },
          zhihuApiKey
        );

        const items = extractZhihuHotListItems(response);
        const text = items.length === 0
          ? "Zhihu hot list is empty."
          : [
              "Current Zhihu hot list:",
              ...items.map((item, index) =>
                `${index + 1}. ${item.title}\n${item.url}\n${getShortText(item.summary || "No summary.")}`
              )
            ].join("\n\n");

        return {
          content: [
            {
              type: "text",
              text
            }
          ],
          structuredContent: {
            count: items.length,
            items
          }
        };
      }
    );

    server.registerTool(
      "zhihu_url_search",
      {
        title: "Zhihu URL Search",
        description: "Search around a shared URL by inferring keywords and host constraints.",
        inputSchema: {
          url: z.string().url(),
          count: z.number().int().min(1).max(10).optional()
        }
      },
      async ({ url, count }) => {
        const parsedUrl = parseSharedUrl(url);
        const inferredQuery = inferQueryFromUrl(parsedUrl);

        if (isZhihuHost(parsedUrl.hostname)) {
          const response = await zhihuGetJson(
            "/api/v1/content/zhihu_search",
            {
              Query: inferredQuery,
              Count: count
            },
            zhihuApiKey
          );

          const items = extractZhihuSearchItems(response);
          const text = items.length === 0
            ? `No Zhihu results inferred from ${parsedUrl.href}.`
            : [
                `Zhihu URL search for ${parsedUrl.href}`,
                `Inferred query: ${inferredQuery}`,
                ...items.map((item, index) =>
                  `${index + 1}. ${item.title} [${item.contentType}] by ${item.authorName}\n${item.url}\n${getShortText(item.contentText)}`
                )
              ].join("\n\n");

          return {
            content: [
              {
                type: "text",
                text
              }
            ],
            structuredContent: {
              url: parsedUrl.href,
              mode: "zhihu_search",
              inferredQuery,
              count: items.length,
              items
            }
          };
        }

        const response = await zhihuGetJson(
          "/api/v1/content/global_search",
          {
            Query: inferredQuery,
            Count: count,
            Filter: buildHostFilter(parsedUrl.hostname),
            SearchDB: "all"
          },
          zhihuApiKey
        );

        const items = extractZhihuSearchItems(response);
        const text = items.length === 0
          ? `No global results inferred from ${parsedUrl.href}.`
          : [
              `URL search for ${parsedUrl.href}`,
              `Inferred query: ${inferredQuery}`,
              `Host filter: ${parsedUrl.hostname}`,
              ...items.map((item, index) =>
                `${index + 1}. ${item.title} [${item.contentType}] by ${item.authorName}\n${item.url}\n${getShortText(item.contentText)}`
              )
            ].join("\n\n");

        return {
          content: [
            {
              type: "text",
              text
            }
          ],
          structuredContent: {
            url: parsedUrl.href,
            mode: "global_search",
            inferredQuery,
            hostFilter: buildHostFilter(parsedUrl.hostname),
            count: items.length,
            items
          }
        };
      }
    );
  }

  return server;
}

class InMemoryClientsStore {
  private readonly clients = new Map<string, OAuthClientInformationFull>();

  async getClient(clientId: string): Promise<OAuthClientInformationFull | undefined> {
    return this.clients.get(clientId);
  }

  async registerClient(clientMetadata: OAuthClientMetadata): Promise<OAuthClientInformationFull> {
    const clientId = randomUUID();
    const clientInformation: OAuthClientInformationFull = {
      ...clientMetadata,
      client_id: clientId,
      client_id_issued_at: Math.floor(Date.now() / 1000)
    };

    this.clients.set(clientId, clientInformation);
    return clientInformation;
  }
}

type AuthorizationCodeRecord = {
  client: OAuthClientInformationFull;
  params: AuthorizationParams;
};

type AccessTokenRecord = {
  clientId: string;
  scopes: string[];
  expiresAt: number;
  resource?: string;
};

class HelloWorldOAuthProvider implements OAuthServerProvider {
  readonly clientsStore = new InMemoryClientsStore();
  private readonly codes = new Map<string, AuthorizationCodeRecord>();
  private readonly tokens = new Map<string, AccessTokenRecord>();

  async authorize(
    client: OAuthClientInformationFull,
    params: AuthorizationParams,
    res: { redirect: (url: string) => void }
  ): Promise<void> {
    const code = randomUUID();
    this.codes.set(code, { client, params });

    const searchParams = new URLSearchParams({ code });
    if (params.state) {
      searchParams.set("state", params.state);
    }

    const redirectUrl = new URL(params.redirectUri);
    redirectUrl.search = searchParams.toString();
    res.redirect(redirectUrl.toString());
  }

  async challengeForAuthorizationCode(
    client: OAuthClientInformationFull,
    authorizationCode: string
  ): Promise<string> {
    const code = this.codes.get(authorizationCode);
    if (!code || code.client.client_id !== client.client_id) {
      throw new Error("Invalid authorization code");
    }

    return code.params.codeChallenge;
  }

  async exchangeAuthorizationCode(
    client: OAuthClientInformationFull,
    authorizationCode: string
  ): Promise<OAuthTokens> {
    const code = this.codes.get(authorizationCode);
    if (!code || code.client.client_id !== client.client_id) {
      throw new Error("Invalid authorization code");
    }

    this.codes.delete(authorizationCode);

    const accessToken = randomUUID();
    const scopes = code.params.scopes ?? ["mcp:tools"];
    const expiresAt = Date.now() + 60 * 60 * 1000;

    this.tokens.set(accessToken, {
      clientId: client.client_id,
      scopes,
      expiresAt,
      resource: code.params.resource?.toString()
    });

    return {
      access_token: accessToken,
      token_type: "bearer",
      expires_in: 3600,
      scope: scopes.join(" ")
    };
  }

  async exchangeRefreshToken(): Promise<OAuthTokens> {
    throw new Error("refresh_token is not implemented");
  }

  async verifyAccessToken(token: string): Promise<AuthInfo> {
    const tokenRecord = this.tokens.get(token);
    if (!tokenRecord || tokenRecord.expiresAt <= Date.now()) {
      throw new Error("Invalid or expired token");
    }

    return {
      token,
      clientId: tokenRecord.clientId,
      scopes: tokenRecord.scopes,
      expiresAt: Math.floor(tokenRecord.expiresAt / 1000),
      resource: tokenRecord.resource ? new URL(tokenRecord.resource) : undefined
    };
  }

  async revokeToken(_client: OAuthClientInformationFull, request: OAuthTokenRevocationRequest): Promise<void> {
    this.tokens.delete(request.token);
  }
}

const provider = new HelloWorldOAuthProvider();
const app = createMcpExpressApp({ host: bindHost });
const authMiddleware = requireBearerAuth({
  verifier: provider,
  requiredScopes: []
});

app.use(
  mcpAuthRouter({
    provider,
    issuerUrl,
    resourceServerUrl: mcpServerUrl,
    scopesSupported: ["mcp:tools"],
    resourceName: "ChatGPT MCP Hello"
  })
);

app.get("/healthz", (_req, res) => {
  res.status(200).json({ ok: true });
});

app.post("/mcp", authMiddleware, async (req, res) => {
  const server = createMcpServer();

  try {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined
    });

    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);

    res.on("close", () => {
      void transport.close();
      void server.close();
    });
  } catch (error) {
    console.error("Failed to handle MCP request", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: {
          code: -32603,
          message: "Internal server error"
        },
        id: null
      });
    }
  }
});

for (const method of ["get", "delete"] as const) {
  app[method]("/mcp", authMiddleware, (_req, res) => {
    res.status(405).json({
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Method not allowed."
      },
      id: null
    });
  });
}

app.listen(port, bindHost, () => {
  console.log(`chatgpt-mcp-hello listening on http://${bindHost}:${port}`);
  console.log(`OAuth issuer: ${issuerUrl.href}`);
  console.log(`MCP resource: ${mcpServerUrl.href}`);
  if (!zhihuApiKey) {
    console.warn("ZHIHU_API_KEY is not set; Zhihu tools are disabled.");
  }
});
