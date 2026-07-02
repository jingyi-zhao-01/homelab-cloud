import { mcpAuthRouter } from "@modelcontextprotocol/sdk/server/auth/router.js";
import { requireBearerAuth } from "@modelcontextprotocol/sdk/server/auth/middleware/bearerAuth.js";

import type { InMemoryOAuthProvider } from "./in-memory-oauth-provider.js";

type McpOAuthRouterOptions = {
  issuerUrl: URL;
  resourceServerUrl: URL;
  resourceName: string;
  scopesSupported?: string[];
};

export function createMcpOAuthMiddleware(provider: InMemoryOAuthProvider) {
  return requireBearerAuth({
    verifier: provider,
    requiredScopes: []
  });
}

export function createMcpOAuthRouter(
  provider: InMemoryOAuthProvider,
  options: McpOAuthRouterOptions
) {
  return mcpAuthRouter({
    provider,
    issuerUrl: options.issuerUrl,
    resourceServerUrl: options.resourceServerUrl,
    scopesSupported: options.scopesSupported ?? ["mcp:tools"],
    resourceName: options.resourceName
  });
}
