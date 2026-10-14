import type {
  AgentEvent,
  AnalysisDetail,
  AnalysisSummary,
  ChaosState,
  ChatDetail,
  ChatSummary,
  ProviderChoice,
  RunSummary,
  RuntimeConfig,
} from "./types";

const TOKEN_KEY = "policy-analytics-token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable: token lives for this page only */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  // X-Access-Token rather than Authorization: CloudFront only forwards Authorization when it is part of
  // the cache key, which a no-cache API behaviour cannot have.
  if (token) headers.set("X-Access-Token", token);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const resp = await fetch(path, { ...init, headers });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export interface PublicConfig {
  token_required: boolean;
  llm_mode: string;
  version: string;
  env: string;
  sample_queries: string[];
}

export interface MessageOptions {
  webContext: boolean;
  provider: ProviderChoice;
}

const messageBody = (query: string, o: MessageOptions) =>
  JSON.stringify({ query, web_context: o.webContext, provider_preference: o.provider === "auto" ? null : o.provider });

export const api = {
  publicConfig: () => request<PublicConfig>("/api/v1/public-config"),
  config: () => request<RuntimeConfig>("/api/v1/config"),
  createAnalysis: (query: string, webContext: boolean) =>
    request<AnalysisSummary>("/api/v1/analyses", {
      method: "POST",
      body: JSON.stringify({ query, web_context: webContext }),
    }),
  listAnalyses: (q?: string) =>
    request<AnalysisSummary[]>(`/api/v1/analyses${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  createChat: (query: string, o: MessageOptions) =>
    request<ChatDetail>("/api/v1/chats", { method: "POST", body: messageBody(query, o) }),
  listChats: (q?: string) => request<ChatSummary[]>(`/api/v1/chats${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getChat: (id: string) => request<ChatDetail>(`/api/v1/chats/${id}`),
  renameChat: (id: string, title: string) =>
    request<ChatSummary>(`/api/v1/chats/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  pinChat: (id: string, pinned: boolean) =>
    request<ChatSummary>(`/api/v1/chats/${id}`, { method: "PATCH", body: JSON.stringify({ pinned }) }),
  deleteChat: (id: string) => request<void>(`/api/v1/chats/${id}`, { method: "DELETE" }),
  sendMessage: (chatId: string, query: string, o: MessageOptions) =>
    request<ChatDetail>(`/api/v1/chats/${chatId}/messages`, { method: "POST", body: messageBody(query, o) }),
  retryTurn: (chatId: string, turn: number) =>
    request<ChatDetail>(`/api/v1/chats/${chatId}/turns/${turn}/retry`, { method: "POST" }),
  summary: (id: string) => request<RunSummary>(`/api/v1/analyses/${id}/summary`),
  getAnalysis: (id: string) => request<AnalysisDetail>(`/api/v1/analyses/${id}`),
  events: (id: string, after = 0) => request<AgentEvent[]>(`/api/v1/analyses/${id}/events?after=${after}`),
  clarify: (id: string, answer: string) =>
    request<{ status: string }>(`/api/v1/analyses/${id}/clarify`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),
  cancel: (id: string) => request(`/api/v1/analyses/${id}/cancel`, { method: "POST" }),
  rerun: (id: string) => request<AnalysisSummary>(`/api/v1/analyses/${id}/rerun`, { method: "POST" }),
  remove: (id: string) => request(`/api/v1/analyses/${id}`, { method: "DELETE" }),
  chaos: () => request<ChaosState>("/api/v1/admin/chaos"),
  setChaos: (body: Partial<ChaosState>) =>
    request<ChaosState>("/api/v1/admin/chaos", { method: "PUT", body: JSON.stringify(body) }),
  exportUrl: (id: string, format: string) => {
    const token = getToken();
    return `/api/v1/analyses/${id}/export?format=${format}${token ? `&token=${encodeURIComponent(token)}` : ""}`;
  },
};

export function wsUrl(id: string, after: number): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const token = getToken();
  return `${proto}://${window.location.host}/ws/analyses/${id}?after=${after}${
    token ? `&token=${encodeURIComponent(token)}` : ""
  }`;
}
