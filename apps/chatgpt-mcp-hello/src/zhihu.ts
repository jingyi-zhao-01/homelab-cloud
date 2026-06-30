const ZHIHU_API_BASE = "https://developer.zhihu.com";

export type ZhihuSearchItem = {
  title: string;
  contentType: string;
  contentId: string;
  contentText: string;
  url: string;
  commentCount: number;
  voteUpCount: number;
  authorName: string;
  authorAvatar: string;
  authorBadge: string;
  authorBadgeText: string;
  editTime: number;
  authorityLevel: string;
  rankingScore?: number;
};

export type ZhihuHotListItem = {
  title: string;
  url: string;
  thumbnailUrl: string;
  summary: string;
};

export function buildZhihuUrl(path: string, params: Record<string, string | number | undefined>): URL {
  const url = new URL(path, ZHIHU_API_BASE);

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  }

  return url;
}

export function createZhihuHeaders(apiKey: string, now = Math.floor(Date.now() / 1000)): Headers {
  return new Headers({
    Authorization: `Bearer ${apiKey}`,
    "X-Request-Timestamp": String(now),
    "Content-Type": "application/json"
  });
}

export async function zhihuGetJson(
  path: string,
  params: Record<string, string | number | undefined>,
  apiKey: string
): Promise<unknown> {
  const response = await fetch(buildZhihuUrl(path, params), {
    method: "GET",
    headers: createZhihuHeaders(apiKey)
  });

  const text = await response.text();
  const json = text ? (JSON.parse(text) as unknown) : {};

  if (!response.ok) {
    throw new Error(`Zhihu API HTTP ${response.status}: ${text}`);
  }

  assertZhihuSuccess(json);
  return json;
}

export function extractZhihuSearchItems(json: unknown): ZhihuSearchItem[] {
  const data = getObjectValue(getObject(json), "Data");
  const items = getArrayValue(data, "Items");

  return items.map((item) => {
    const record = getObject(item);
    return {
      title: getString(record, "Title"),
      contentType: getString(record, "ContentType"),
      contentId: getString(record, "ContentID"),
      contentText: getString(record, "ContentText"),
      url: getString(record, "Url"),
      commentCount: getNumber(record, "CommentCount"),
      voteUpCount: getNumber(record, "VoteUpCount"),
      authorName: getString(record, "AuthorName"),
      authorAvatar: getString(record, "AuthorAvatar"),
      authorBadge: getString(record, "AuthorBadge"),
      authorBadgeText: getString(record, "AuthorBadgeText"),
      editTime: getNumber(record, "EditTime"),
      authorityLevel: getString(record, "AuthorityLevel"),
      rankingScore: getOptionalNumber(record, "RankingScore")
    };
  });
}

export function extractZhihuHotListItems(json: unknown): ZhihuHotListItem[] {
  const root = getObject(json);
  const items = getArrayValue(root, "items");

  return items.map((item) => {
    const record = getObject(item);
    return {
      title: getString(record, "title"),
      url: getString(record, "url"),
      thumbnailUrl: getString(record, "thumbnail_url"),
      summary: getString(record, "summary")
    };
  });
}

export function parseSharedUrl(rawUrl: string): URL {
  return new URL(rawUrl.trim());
}

export function isZhihuHost(hostname: string): boolean {
  return hostname === "zhihu.com" || hostname.endsWith(".zhihu.com");
}

export function buildHostFilter(hostname: string): string {
  return `host=="${hostname}"`;
}

export function inferQueryFromUrl(url: URL): string {
  const fromSearch = url.searchParams.get("q") ?? url.searchParams.get("query") ?? url.searchParams.get("keyword");
  if (fromSearch) {
    return normalizeQuery(fromSearch);
  }

  const candidates = url.pathname
    .split("/")
    .map((segment) => decodeURIComponent(segment))
    .flatMap((segment) => segment.split(/[-_+]/))
    .map((segment) => segment.trim())
    .filter(Boolean)
    .filter((segment) => !/^\d+$/.test(segment))
    .filter((segment) => !["question", "answer", "p", "articles", "zvideo"].includes(segment.toLowerCase()));

  const compact = candidates.join(" ").trim();
  return compact ? normalizeQuery(compact) : url.hostname;
}

function normalizeQuery(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, 100);
}

function assertZhihuSuccess(json: unknown): void {
  const root = getObject(json);
  const errorCode = getOptionalNumber(root, "Code") ?? getOptionalNumber(root, "code") ?? 0;
  if (errorCode !== 0) {
    const errorMessage = getOptionalString(root, "Message") ?? getOptionalString(root, "message") ?? "unknown error";
    throw new Error(`Zhihu API error ${errorCode}: ${errorMessage}`);
  }
}

function getObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Expected object response from Zhihu API");
  }

  return value as Record<string, unknown>;
}

function getObjectValue(value: Record<string, unknown>, key: string): Record<string, unknown> {
  return getObject(value[key]);
}

function getArrayValue(value: Record<string, unknown>, key: string): unknown[] {
  const target = value[key];
  if (!Array.isArray(target)) {
    throw new Error(`Expected array field ${key}`);
  }

  return target;
}

function getString(value: Record<string, unknown>, key: string): string {
  const target = value[key];
  if (typeof target !== "string") {
    throw new Error(`Expected string field ${key}`);
  }

  return target;
}

function getOptionalString(value: Record<string, unknown>, key: string): string | undefined {
  const target = value[key];
  return typeof target === "string" ? target : undefined;
}

function getNumber(value: Record<string, unknown>, key: string): number {
  const target = value[key];
  if (typeof target !== "number") {
    throw new Error(`Expected number field ${key}`);
  }

  return target;
}

function getOptionalNumber(value: Record<string, unknown>, key: string): number | undefined {
  const target = value[key];
  return typeof target === "number" ? target : undefined;
}
