import assert from "node:assert/strict";
import test from "node:test";

import { z } from "zod";

import { localMcpSchema, remoteJsonMcpSchema, resolveMcpInputSchema } from "./mcp-schema.js";

test("resolveMcpInputSchema keeps local schema objects intact", () => {
  const shape = {
    query: z.string()
  };

  assert.equal(resolveMcpInputSchema(localMcpSchema(shape)), shape);
});

test("resolveMcpInputSchema converts remote JSON Schema into passthrough object", () => {
  const resolved = resolveMcpInputSchema(remoteJsonMcpSchema({
    type: "object",
    properties: {
      query: {
        type: "string"
      }
    }
  }));

  const parsed = (resolved as z.ZodTypeAny).parse({
    anything: "goes"
  });

  assert.deepEqual(parsed, {
    anything: "goes"
  });
});
