import { useEffect, useState } from "react";
import { chatApi } from "../api/chat";

/** LLM providers that have been configured on the backend. */
export function useProviders() {
  const [providers, setProviders] = useState([]);

  useEffect(() => {
    chatApi
      .providers()
      .then((list) => setProviders(list.filter((provider) => provider.configured)))
      .catch(() => undefined); // optional: the default model still works without this list
  }, []);

  return providers;
}
