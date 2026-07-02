import { randomUUID } from "node:crypto";

import type {
  AuthorizationParams,
  OAuthServerProvider
} from "@modelcontextprotocol/sdk/server/auth/provider.js";
import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import type {
  OAuthClientInformationFull,
  OAuthClientMetadata,
  OAuthTokenRevocationRequest,
  OAuthTokens
} from "@modelcontextprotocol/sdk/shared/auth.js";

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

export class InMemoryOAuthProvider implements OAuthServerProvider {
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
