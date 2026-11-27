import { request } from "./client";

export const authApi = {
  register: (email, password, name) =>
    request("/auth/register", {
      method: "POST",
      body: { email, password, name: name || undefined },
      auth: false,
    }),
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: { email, password }, auth: false }),
  me: () => request("/auth/me"),
};
