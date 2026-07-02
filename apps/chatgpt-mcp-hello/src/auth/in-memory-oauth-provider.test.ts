import assert from "node:assert/strict";
import test from "node:test";

import type { AuthorizationParams } from "@modelcontextprotocol/sdk/server/auth/provider.js";

import { InMemoryOAuthProvider } from "./in-memory-oauth-provider.js";

test("InMemoryOAuthProvider completes auth code flow and verifies token", async () => {
  const provider = new InMemoryOAuthProvider();
  const client = await provider.clientsStore.registerClient({
    client_name: "test-client",
    redirect_uris: ["https://example.com/callback"]
  });

  const params = {
    redirectUri: "https://example.com/callback",
    codeChallenge: "challenge-123",
    state: "state-abc",
    scopes: ["mcp:tools"],
    resource: new URL("https://mcp-hello.example.com/mcp")
  } as AuthorizationParams;

  let redirectUrl = "";
  await provider.authorize(client, params, {
    redirect(url: string) {
      redirectUrl = url;
    }
  });

  const code = new URL(redirectUrl).searchParams.get("code");
  assert.ok(code);
  assert.equal(new URL(redirectUrl).searchParams.get("state"), "state-abc");
  assert.equal(await provider.challengeForAuthorizationCode(client, code), "challenge-123");

  const tokens = await provider.exchangeAuthorizationCode(client, code);
  assert.equal(tokens.token_type, "bearer");
  assert.equal(tokens.scope, "mcp:tools");

  const authInfo = await provider.verifyAccessToken(tokens.access_token);
  assert.equal(authInfo.clientId, client.client_id);
  assert.equal(authInfo.resource?.href, "https://mcp-hello.example.com/mcp");
});
