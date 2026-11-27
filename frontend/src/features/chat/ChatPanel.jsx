import { useEffect, useRef, useState } from "react";
import Alert from "../../components/ui/Alert";
import { useChat } from "../../hooks/useChat";
import { QUESTION_MIN_LENGTH } from "../../lib/constants";
import ChatHeader from "./ChatHeader";
import Composer from "./Composer";
import EmptyChat from "./EmptyChat";
import IndexingState from "./IndexingState";
import Thread from "./Thread";
import styles from "./ChatPanel.module.css";

/** Conversation view for one repository. Render with `key={repo.id}` so state never crosses repositories. */
export default function ChatPanel({
  repo,
  providers,
  mode,
  onModeChange,
  provider,
  onProviderChange,
  onOpenSource,
  onOpenMenu,
  onRepoUpdated,
  onRepoDeleted,
}) {
  const ready = repo.status === "ready";
  const chat = useChat(repo.id, ready);
  const [input, setInput] = useState("");
  const [actionError, setActionError] = useState(null);
  const end = useRef(null);
  const inputRef = useRef(null);
  const hasItems = chat.items.length > 0;
  const canSend = ready && !chat.busy && input.trim().length >= QUESTION_MIN_LENGTH;
  const error = actionError || chat.historyError;

  useEffect(() => {
    if (hasItems) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat.items, hasItems]);

  function send() {
    if (!canSend) return;
    setInput("");
    void chat.ask(input.trim(), mode, provider);
  }

  function useExample(example) {
    setInput(example);
    inputRef.current?.focus();
  }

  return (
    <section className={styles.panel}>
      <ChatHeader
        repo={repo}
        conversations={chat.conversations}
        conversationId={chat.conversationId}
        onOpenConversation={chat.openConversation}
        onNewChat={chat.startNew}
        canStartNew={hasItems}
        onOpenMenu={onOpenMenu}
        onRepoUpdated={onRepoUpdated}
        onRepoDeleted={onRepoDeleted}
        onError={setActionError}
      />

      <div className={styles.scroller}>
        <div className={styles.column} aria-live="polite">
          {error && <Alert tone="error">{error}</Alert>}
          {!ready && <IndexingState repo={repo} />}
          {ready && !hasItems && <EmptyChat repoName={repo.name} mode={mode} onPickExample={useExample} />}
          <Thread items={chat.items} onOpenSource={onOpenSource} />
          <div ref={end} />
        </div>
      </div>

      <Composer
        ref={inputRef}
        repoName={repo.name}
        ready={ready}
        failed={repo.status === "failed"}
        busy={chat.busy}
        canSend={canSend}
        value={input}
        onChange={setInput}
        onSend={send}
        mode={mode}
        onModeChange={onModeChange}
        providers={providers}
        provider={provider}
        onProviderChange={onProviderChange}
        scanning={chat.scanning}
        onScan={chat.scanDuplicates}
      />
    </section>
  );
}
