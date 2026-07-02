import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

type RemoteTool = {
  name: string;
  title?: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
};

export type ProxiedTool = {
  localName: string;
  remoteName: string;
  title?: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
};

function isArchMcpEnabled(): boolean {
  return process.env.ARCH_MCP_ENABLED !== "false";
}

function getArchMcpCommand(): string {
  return process.env.ARCH_MCP_COMMAND ?? "arch-ops-server";
}

export function buildProxiedTools(remoteTools: RemoteTool[], reservedNames: Iterable<string>): ProxiedTool[] {
  const seen = new Set(reservedNames);

  return remoteTools.map((tool) => {
    let localName = tool.name;

    if (seen.has(localName)) {
      localName = `arch_${tool.name}`;
    }

    let suffix = 2;
    while (seen.has(localName)) {
      localName = `arch_${tool.name}_${suffix}`;
      suffix += 1;
    }

    seen.add(localName);

    return {
      localName,
      remoteName: tool.name,
      title: tool.title,
      description: tool.description,
      inputSchema: tool.inputSchema
    };
  });
}

export class ArchMcpBridge {
  private readonly enabled = isArchMcpEnabled();
  private readonly command = getArchMcpCommand();
  private client?: Client;
  private transport?: StdioClientTransport;
  private connectPromise?: Promise<void>;
  private remoteTools?: RemoteTool[];
  private warnedUnavailable = false;

  async listTools(reservedNames: Iterable<string>): Promise<ProxiedTool[]> {
    if (!this.enabled) {
      return [];
    }

    try {
      await this.ensureConnected();
      if (!this.remoteTools) {
        const { tools } = await this.client!.listTools();
        this.remoteTools = tools;
      }

      return buildProxiedTools(this.remoteTools, reservedNames);
    } catch (error) {
      this.warnUnavailable(error);
      return [];
    }
  }

  async callTool(remoteName: string, args: Record<string, unknown>): Promise<Awaited<ReturnType<Client["callTool"]>>> {
    await this.ensureConnected();
    return this.client!.callTool({
      name: remoteName,
      arguments: args
    });
  }

  private async ensureConnected(): Promise<void> {
    if (!this.enabled) {
      throw new Error("arch-mcp is disabled");
    }

    if (this.client) {
      return;
    }

    if (!this.connectPromise) {
      this.connectPromise = this.connect().catch((error) => {
        this.reset();
        throw error;
      });
    }

    await this.connectPromise;
  }

  private async connect(): Promise<void> {
    const transport = new StdioClientTransport({
      command: this.command,
      stderr: "pipe"
    });

    transport.stderr?.on("data", (chunk) => {
      const message = chunk.toString().trim();
      if (message) {
        console.error(`[arch-mcp] ${message}`);
      }
    });

    transport.onclose = () => {
      this.reset();
    };

    const client = new Client(
      {
        name: "chatgpt-mcp-hello-arch-bridge",
        version: "0.1.0"
      },
      {
        capabilities: {}
      }
    );

    await client.connect(transport);

    this.transport = transport;
    this.client = client;
    this.connectPromise = undefined;
    this.warnedUnavailable = false;
  }

  private reset(): void {
    this.client = undefined;
    this.transport = undefined;
    this.connectPromise = undefined;
    this.remoteTools = undefined;
  }

  private warnUnavailable(error: unknown): void {
    if (this.warnedUnavailable) {
      return;
    }

    this.warnedUnavailable = true;
    console.warn(`arch-mcp bridge unavailable (${this.command}):`, error);
  }
}

export const archMcpBridge = new ArchMcpBridge();
