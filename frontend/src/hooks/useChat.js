import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi } from "../api/chat";
import { errorMessage } from "../api/client";
import { reposApi } from "../api/repos";

let sequence = 0;
const nextId = () => `item-${++sequence}`;

/**
 * Chat thread state for one repository. Thread items are one of:
 * { kind: "result", result } | { kind: "pending", question, mode }
 * | { kind: "error", question, message } | { kind: "duplicates", report }
 */
export function useChat(repoId, ready) {
  const [items, setItems] = useState([]);
  const [conversationId, setConversationId] = useState(undefined);
  const [conversations, setConversations] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  // Bumped whenever the thread is replaced, so late responses are not added to the wrong conversation.
  const thread = useRef(0);

  const busy = scanning || items.some((item) => item.kind === "pending");

  const refreshConversations = useCallback(() => {
    chatApi
      .conversations(repoId)
      .then(setConversations)
      .catch(() => undefined); // history is optional
  }, [repoId]);

  const replaceThread = useCallback((nextItems, nextConversationId) => {
    thread.current += 1;
    setItems(nextItems);
    setConversationId(nextConversationId);
    setHistoryError(null);
  }, []);

  const startNew = useCallback(() => replaceThread([], undefined), [replaceThread]);

  // Start fresh when indexing finishes or restarts.
  useEffect(() => {
    startNew();
    if (ready) refreshConversations();
  }, [ready, refreshConversations, startNew]);

  const ask = useCallback(
    async (question, mode, provider) => {
      const id = nextId();
      const startedIn = thread.current;
      const replace = (item) => setItems((list) => list.map((old) => (old.id === id ? item : old)));
      setItems((list) => [...list, { id, kind: "pending", question, mode }]);
      try {
        const result = await chatApi.query(repoId, {
          question,
          mode,
          conversation_id: conversationId,
          provider: provider || undefined,
        });
        if (startedIn === thread.current) {
          setConversationId(result.conversation_id);
          replace({ id, kind: "result", result });
        }
        refreshConversations();
      } catch (err) {
        replace({ id, kind: "error", question, message: errorMessage(err, "Something went wrong.") });
      }
    },
    [repoId, conversationId, refreshConversations],
  );

  const scanDuplicates = useCallback(async () => {
    const startedIn = thread.current;
    const append = (item) => {
      if (startedIn === thread.current) setItems((list) => [...list, { id: nextId(), ...item }]);
    };
    setScanning(true);
    try {
      append({ kind: "duplicates", report: await reposApi.duplicates(repoId) });
    } catch (err) {
      append({ kind: "error", question: "Duplicate scan", message: errorMessage(err, "Scan failed") });
    } finally {
      setScanning(false);
    }
  }, [repoId]);

  const openConversation = useCallback(
    async (id) => {
      if (!id) {
        startNew();
        return;
      }
      try {
        const history = await chatApi.history(repoId, id);
        replaceThread(
          history.map((result) => ({ id: nextId(), kind: "result", result })),
          id,
        );
      } catch (err) {
        setHistoryError(errorMessage(err, "Could not open that conversation."));
      }
    },
    [repoId, replaceThread, startNew],
  );

  return {
    items,
    conversationId,
    conversations,
    historyError,
    scanning,
    busy,
    ask,
    scanDuplicates,
    openConversation,
    startNew,
  };
}
