import assert from "node:assert/strict";
import test from "node:test";

import { buildProxiedTools } from "./arch-mcp.js";

test("buildProxiedTools keeps upstream names unless they collide", () => {
  const proxied = buildProxiedTools(
    [
      { name: "hello_world" },
      { name: "search_archwiki" },
      { name: "hello_world" }
    ],
    ["hello_world", "zhihu_search"]
  );

  assert.deepEqual(
    proxied.map((tool) => tool.localName),
    ["arch_hello_world", "search_archwiki", "arch_hello_world_2"]
  );
});
