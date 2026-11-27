import { tokenStore } from "../lib/tokenStore";

// In production builds VITE_API_URL is mandatory (set in Vercel). Localhost is only a dev-server fallback.
const configured = import.meta.env.VITE_API_URL?.trim();
export const API_BASE = (configured || (import.meta.env.DEV ? "http://localhost:8000" : "")).replace(/\/+$/, "");
export const API_CONFIGURED = API_BASE.length > 0;

export class ApiError extends Error {
  constructor(message, status, code = "error") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** The message to show for a failed request, with a fallback for unexpected errors. */
export const errorMessage = (error, fallback) => (error instanceof ApiError ? error.message : fallback);

let onUnauthorized = null;
export const setUnauthorizedHandler = (handler) => {
  onUnauthorized = handler;
};

/**
 * Send a request to the backend and return the parsed JSON body.
 * @param {string} path  Path below `/api`, e.g. "/repos".
 * @param {{ method?: string, body?: object, auth?: boolean }} [options]
 */
export async function request(path, { method = "GET", body, auth = true } = {}) {
  if (!API_CONFIGURED) {
    throw new ApiError(
      "The frontend is missing VITE_API_URL (the backend address). Set it in your Vercel project settings and redeploy.",
      0,
      "config",
    );
  }

  const headers = { Accept: "application/json" };
  const payload = body === undefined ? undefined : JSON.stringify(body);
  if (payload) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (token && auth) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE}/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(
      "Cannot reach the server. If it was idle it may still be waking up. Try again in a moment.",
      0,
      "network",
    );
  }
  if (response.status === 204) return undefined;

  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON body */
  }

  if (!response.ok) {
    if (response.status === 401 && auth) onUnauthorized?.();
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (${response.status})`;
    throw new ApiError(detail, response.status, data?.code ?? "error");
  }
  return data;
}
