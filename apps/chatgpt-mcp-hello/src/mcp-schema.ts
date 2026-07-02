import { z } from "zod";

type JsonSchema = Record<string, unknown>;
type LocalSchemaShape = z.ZodRawShape | z.ZodTypeAny;

export type LocalMcpToolSchema<InputSchema extends LocalSchemaShape = LocalSchemaShape> = {
  kind: "local";
  schema: InputSchema;
};

export type JsonMcpToolSchema = {
  kind: "json-schema";
  schema: JsonSchema;
};

export type EmptyMcpToolSchema = {
  kind: "none";
};

export type McpToolSchema = LocalMcpToolSchema | JsonMcpToolSchema | EmptyMcpToolSchema;

export function localMcpSchema<InputSchema extends LocalSchemaShape>(
  schema: InputSchema
): LocalMcpToolSchema<InputSchema> {
  return {
    kind: "local",
    schema
  };
}

export function remoteJsonMcpSchema(schema?: JsonSchema): JsonMcpToolSchema | EmptyMcpToolSchema {
  if (!schema) {
    return {
      kind: "none"
    };
  }

  return {
    kind: "json-schema",
    schema
  };
}

export function noMcpSchema(): EmptyMcpToolSchema {
  return {
    kind: "none"
  };
}

export function resolveMcpInputSchema<InputSchema extends LocalSchemaShape>(
  schema: LocalMcpToolSchema<InputSchema>
): InputSchema;
export function resolveMcpInputSchema(schema: JsonMcpToolSchema | EmptyMcpToolSchema): z.ZodObject<{}, z.core.$loose>;
export function resolveMcpInputSchema(schema: McpToolSchema): LocalSchemaShape {
  if (schema.kind === "local") {
    return schema.schema;
  }

  // ponytail: MCP TS SDK registerTool wants Zod/raw shape, not JSON Schema.
  // We still keep the upstream JSON Schema in our contract so callers have one interface.
  return z.object({}).passthrough();
}
