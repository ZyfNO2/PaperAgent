// Session 52: API client 基线
// - GET/POST 统一 JSON
// - HTTP error 抛 ApiError (含 status + body)
// - 任意请求可挂 AbortSignal
// - 后续 S55 接 RAG/ThesisEval 时再加 streaming/timeout helper

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export interface ApiRequestOptions {
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined>;
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: ApiRequestOptions["query"]): string {
  const base = path.startsWith("/") ? path : `/${path}`;
  if (!query) return base;
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined) continue;
    usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `${base}?${qs}` : base;
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  body: unknown | undefined,
  opts: ApiRequestOptions = {},
): Promise<T> {
  const url = buildUrl(path, opts.query);
  const init: RequestInit = {
    method,
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(opts.headers ?? {}),
    },
    signal: opts.signal,
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const resp = await fetch(url, init);
  const text = await resp.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (!resp.ok) {
    throw new ApiError(
      resp.status,
      `${method} ${url} → ${resp.status} ${resp.statusText}`,
      parsed,
    );
  }
  return parsed as T;
}

export const apiClient = {
  get: <T,>(path: string, opts?: ApiRequestOptions) =>
    request<T>("GET", path, undefined, opts),
  post: <T,>(path: string, body?: unknown, opts?: ApiRequestOptions) =>
    request<T>("POST", path, body, opts),
};
