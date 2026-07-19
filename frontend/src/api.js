const API_BASE = "http://localhost:8000";
const TOKEN_KEY = "ai_swe_token";

export function saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = "Request failed";
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  signup: (name, email, password) =>
    request("/api/auth/signup", { method: "POST", body: { name, email, password }, auth: false }),
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", body: { email, password }, auth: false }),
  me: () => request("/api/auth/me"),
  dashboard: () => request("/api/auth/dashboard"),

  indexRepo: (repo_url) => request("/api/repos/index", { method: "POST", body: { repo_url } }),
  ask: (repo_id, question) => request("/api/ask", { method: "POST", body: { repo_id, question } }),
  fileAction: (endpoint, repo_id, file_path) =>
    request(endpoint, { method: "POST", body: { repo_id, file_path } }),
};
