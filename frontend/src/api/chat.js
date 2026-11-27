import { request } from "./client";

export const chatApi = {
  /** @param {{ question: string, mode: string, conversation_id?: string, provider?: string }} body */
  query: (repoId, body) => request(`/repos/${repoId}/query`, { method: "POST", body }),
  conversations: (repoId) => request(`/repos/${repoId}/conversations`),
  history: (repoId, conversationId) => request(`/repos/${repoId}/history?conversation_id=${conversationId}`),
  providers: () => request("/llm/providers"),
};
