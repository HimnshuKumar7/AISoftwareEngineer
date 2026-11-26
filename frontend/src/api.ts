import type {
  ConversationSummary, DuplicateReport, Mode, ProviderInfo, QueryResult, Repo, User,
} from "./types";

// In production builds VITE_API_URL is mandatory (set in Vercel). Localhost is only a dev-server fallback.
const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
export const API_BASE = (configured || (import.meta.env.DEV ? "http://localhost:8000" : "")).replace(/\/+$/, "");
export const API_CONFIGURED = API_BASE.length > 0;

const TOKEN_KEY = "ase.token";

export const tokenStore = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* storage unavailable */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ } },
};

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(message: string, status: number, code = "error") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: (() => void) | null) => { onUnauthorized = fn; };

async function request<T>(path: string, init: RequestInit & { auth?: boolean } = {}): Promise<T> {
  if (!API_CONFIGURED) {
    throw new ApiError("The frontend is missing VITE_API_URL (the backend address). Set it in your Vercel project settings and redeploy.", 0, "config");
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (token && init.auth !== false) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api${path}`, { ...init, headers: { ...headers, ...(init.headers as Record<string, string> | undefined) } });
  } catch {
    throw new ApiError("Cannot reach the server. If it was idle it may still be waking up. Try again in a moment.", 0, "network");
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    if (res.status === 401 && init.auth !== false && onUnauthorized) onUnauthorized();
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (${res.status})`;
    throw new ApiError(detail, res.status, data?.code ?? "error");
  }
  return data as T;
}

const post = <T>(path: string, body?: unknown, auth = true) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), auth });

export const api = {
  register: (email: string, password: string, name?: string) =>
    post<{ access_token: string; user: User }>("/auth/register", { email, password, name: name || undefined }, false),
  login: (email: string, password: string) =>
    post<{ access_token: string; user: User }>("/auth/login", { email, password }, false),
  me: () => request<User>("/auth/me"),

  listRepos: () => request<Repo[]>("/repos"),
  getRepo: (id: string) => request<Repo>(`/repos/${id}`),
  addRepo: (url: string, branch?: string) => post<Repo>("/repos", { url, branch: branch || undefined }),
  deleteRepo: (id: string) => request<void>(`/repos/${id}`, { method: "DELETE" }),
  reindex: (id: string) => post<Repo>(`/repos/${id}/reindex`),
  duplicates: (id: string) => request<DuplicateReport>(`/repos/${id}/duplicates?limit=25`),

  query: (id: string, body: { question: string; mode: Mode; conversation_id?: string; provider?: string }) =>
    post<QueryResult>(`/repos/${id}/query`, body),
  conversations: (id: string) => request<ConversationSummary[]>(`/repos/${id}/conversations`),
  history: (id: string, conversationId: string) =>
    request<QueryResult[]>(`/repos/${id}/history?conversation_id=${conversationId}`),
  providers: () => request<ProviderInfo[]>("/llm/providers"),
};
