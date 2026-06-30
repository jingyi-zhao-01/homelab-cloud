import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHostFilter,
  buildZhihuUrl,
  createZhihuHeaders,
  extractZhihuHotListItems,
  extractZhihuSearchItems,
  inferQueryFromUrl,
  isZhihuHost,
  parseSharedUrl
} from "./zhihu.js";

test("buildZhihuUrl encodes query params", () => {
  const url = buildZhihuUrl("/api/v1/content/global_search", {
    Query: "RAG",
    Count: 5,
    SearchDB: "all"
  });

  assert.equal(url.toString(), "https://developer.zhihu.com/api/v1/content/global_search?Query=RAG&Count=5&SearchDB=all");
});

test("createZhihuHeaders includes bearer token and timestamp", () => {
  const headers = createZhihuHeaders("secret", 1742822400);

  assert.equal(headers.get("Authorization"), "Bearer secret");
  assert.equal(headers.get("X-Request-Timestamp"), "1742822400");
  assert.equal(headers.get("Content-Type"), "application/json");
});

test("extractZhihuSearchItems normalizes official response shape", () => {
  const items = extractZhihuSearchItems({
    Code: 0,
    Message: "success",
    Data: {
      HasMore: false,
      Items: [
        {
          Title: "RAG 评测方法综述",
          ContentType: "Article",
          ContentID: "123456789",
          ContentText: "本文介绍了主流 RAG 评测框架。",
          Url: "https://zhuanlan.zhihu.com/p/123456789",
          CommentCount: 15,
          VoteUpCount: 128,
          AuthorName: "张三",
          AuthorAvatar: "https://picx.zhimg.com/example.jpg",
          AuthorBadge: "",
          AuthorBadgeText: "",
          EditTime: 1710000000,
          AuthorityLevel: "2",
          RankingScore: 0.98
        }
      ]
    }
  });

  assert.equal(items.length, 1);
  assert.equal(items[0]?.title, "RAG 评测方法综述");
  assert.equal(items[0]?.rankingScore, 0.98);
});

test("extractZhihuHotListItems normalizes official response shape", () => {
  const items = extractZhihuHotListItems({
    code: 0,
    message: "success",
    total: 1,
    item_count: 1,
    items: [
      {
        title: "如何评价某个热点问题？",
        url: "https://www.zhihu.com/question/123456789",
        thumbnail_url: "https://pic1.zhimg.com/example.jpg",
        summary: "这是该问题的内容摘要"
      }
    ]
  });

  assert.equal(items.length, 1);
  assert.equal(items[0]?.title, "如何评价某个热点问题？");
  assert.equal(items[0]?.summary, "这是该问题的内容摘要");
});

test("parseSharedUrl and isZhihuHost detect Zhihu links", () => {
  const url = parseSharedUrl("https://zhuanlan.zhihu.com/p/18698154193");

  assert.equal(url.hostname, "zhuanlan.zhihu.com");
  assert.equal(isZhihuHost(url.hostname), true);
});

test("inferQueryFromUrl prefers explicit query params", () => {
  const url = parseSharedUrl("https://example.com/search?q=RAG%20evaluation");

  assert.equal(inferQueryFromUrl(url), "RAG evaluation");
});

test("inferQueryFromUrl falls back to cleaned path segments", () => {
  const url = parseSharedUrl("https://www.zhihu.com/question/123456789/how-to-use-rag");

  assert.equal(inferQueryFromUrl(url), "how to use rag");
});

test("buildHostFilter produces global_search filter syntax", () => {
  assert.equal(buildHostFilter("example.com"), 'host=="example.com"');
});
