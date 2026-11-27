import { request } from "./client";

export const reposApi = {
  list: () => request("/repos"),
  add: (url, branch) => request("/repos", { method: "POST", body: { url, branch: branch || undefined } }),
  remove: (id) => request(`/repos/${id}`, { method: "DELETE" }),
  reindex: (id) => request(`/repos/${id}/reindex`, { method: "POST" }),
  duplicates: (id) => request(`/repos/${id}/duplicates?limit=25`),
};
