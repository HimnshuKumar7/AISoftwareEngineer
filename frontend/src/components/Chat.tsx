import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api";
import { ACTIVE_STATUSES, type ConversationSummary, type DuplicateReport, type Mode, type ProviderInfo, type QueryResult, type Repo } from "../types";
import DuplicatesReport from "./DuplicatesReport";
import Message from "./Message";
import type { ActiveSource } from "./SourcePanel";
import StatusBadge from "./StatusBadge";

type Item =
  | { id: string; kind: "result"; result: QueryResult }
  | { id: string; kind: "pending"; question: string; mode: Mode }
  | { id: string; kind: "error"; question: string; message: string }
  | { id: string; kind: "dups"; report: DuplicateReport };

const MODES: { id: Mode; label: string; hint: string; examples: string[] }[] = [
  { id: "qa", label: "Ask", hint: "Repository-aware Q&A", examples: ["How is authentication implemented?", "Where are database connections created?"] },
  { id: "explain", label: "Explain", hint: "Document & explain code", examples: ["Explain how request routing works", "Document the main entry point"] },
  { id: "optimize", label: "Optimize", hint: "Optimization suggestions", examples: ["Find performance problems in the data loading code", "How could the main loop be simplified?"] },
  { id: "duplicates", label: "Duplicates", hint: "Duplicate-code analysis", examples: ["Is there duplicated validation logic?", "Find copy-pasted helper functions"] },
];

let seq = 0;
const nid = () => `i${++seq}`;

export default function Chat({ repo, onOpenSource }: { repo: Repo; onOpenSource: (a: ActiveSource) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [mode, setMode] = useState<Mode>("qa");
  const [input, setInput] = useState("");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [provider, setProvider] = useState("");
  const [scanning, setScanning] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const ready = repo.status === "ready";
  const busy = items.some((i) => i.kind === "pending") || scanning;

  const refreshConversations = useCallback(() => {
    api.conversations(repo.id).then(setConversations).catch(() => undefined);
  }, [repo.id]);

  // Reset the chat whenever another repository is selected (conversations are repository-scoped).
  useEffect(() => {
    setItems([]); setConversationId(undefined); setInput("");
    if (ready) refreshConversations();
  }, [repo.id, ready, refreshConversations]);

  useEffect(() => { api.providers().then(setProviders).catch(() => undefined); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items]);

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const question = input.trim();
    if (question.length < 3 || !ready || busy) return;
    const pid = nid();
    setInput("");
    setItems((x) => [...x, { id: pid, kind: "pending", question, mode }]);
    try {
      const result = await api.query(repo.id, { question, mode, conversation_id: conversationId, provider: provider || undefined });
      setConversationId(result.conversation_id);
      setItems((x) => x.map((i) => (i.id === pid ? { id: pid, kind: "result", result } : i)));
      refreshConversations();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setItems((x) => x.map((i) => (i.id === pid ? { id: pid, kind: "error", question, message } : i)));
    }
  }

  async function scanDuplicates() {
    setScanning(true);
    try {
      const report = await api.duplicates(repo.id);
      setItems((x) => [...x, { id: nid(), kind: "dups", report }]);
    } catch (err) {
      setItems((x) => [...x, { id: nid(), kind: "error", question: "Duplicate scan", message: err instanceof ApiError ? err.message : "Scan failed" }]);
    } finally { setScanning(false); }
  }

  async function loadConversation(id: string) {
    if (!id) { setItems([]); setConversationId(undefined); return; }
    try {
      const hist = await api.history(repo.id, id);
      setConversationId(id);
      setItems(hist.map((h) => ({ id: nid(), kind: "result" as const, result: h })));
    } catch { /* ignore */ }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }
  }

  const current = MODES.find((m) => m.id === mode)!;
  const configured = providers.filter((p) => p.configured);

  return (
    <section className="chat">
      <header className="chat-head">
        <div className="chat-title">
          <h2>{repo.owner}/{repo.name}</h2>
          <div className="muted small">
            <StatusBadge status={repo.status} />{" "}
            {ready && <>{repo.file_count} files · {repo.chunk_count.toLocaleString()} chunks · {Object.keys(repo.languages).length} languages
              {repo.commit_sha ? <> · <span className="mono">{repo.commit_sha.slice(0, 7)}</span></> : null}</>}
          </div>
        </div>
        <div className="chat-tools">
          {conversations.length > 0 && (
            <select aria-label="Conversation history" value={conversationId ?? ""} onChange={(e) => void loadConversation(e.target.value)}>
              <option value="">New conversation</option>
              {conversations.map((c) => <option key={c.conversation_id} value={c.conversation_id}>{c.title}</option>)}
            </select>
          )}
          <button className="btn small" onClick={() => { setItems([]); setConversationId(undefined); }} disabled={items.length === 0}>New chat</button>
        </div>
      </header>

      <div className="thread" aria-live="polite">
        {!ready && (
          <div className="empty-state">
            {ACTIVE_STATUSES.includes(repo.status) ? (
              <>
                <h3>Indexing in progress</h3>
                <p className="muted">{repo.status_message || "Working…"}</p>
                <div className="progress big"><span style={{ width: `${Math.max(4, repo.progress)}%` }} /></div>
                <p className="muted small">Clone → Tree-sitter parse → MiniLM embeddings → FAISS index. You can ask questions as soon as it is ready.</p>
              </>
            ) : (
              <>
                <h3>Indexing failed</h3>
                <p className="error-text">{repo.status_message}</p>
                <p className="muted small">Use “Re-index” in the sidebar to retry.</p>
              </>
            )}
          </div>
        )}

        {ready && items.length === 0 && (
          <div className="empty-state">
            <h3>Ask anything about {repo.name}</h3>
            <p className="muted">Answers are grounded in retrieved code and cite file paths and line numbers.</p>
            <div className="examples">
              {current.examples.map((ex) => <button key={ex} className="chip" onClick={() => setInput(ex)}>{ex}</button>)}
            </div>
          </div>
        )}

        {items.map((it) => {
          if (it.kind === "result") return <Message key={it.id} result={it.result} onOpen={onOpenSource} />;
          if (it.kind === "dups") return <DuplicatesReport key={it.id} report={it.report} />;
          if (it.kind === "pending") {
            return (
              <div key={it.id}>
                <div className="msg user"><span className="tag">{MODES.find((m) => m.id === it.mode)?.label}</span><p>{it.question}</p></div>
                <div className="msg assistant"><span className="typing"><i /><i /><i /></span> <span className="muted small">Planning, retrieving, answering…</span></div>
              </div>
            );
          }
          return (
            <div key={it.id}>
              <div className="msg user"><p>{it.question}</p></div>
              <div className="msg assistant"><div className="alert error" role="alert">{it.message}</div></div>
            </div>
          );
        })}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={send}>
        <div className="modes" role="tablist" aria-label="Mode">
          {MODES.map((m) => (
            <button type="button" key={m.id} role="tab" aria-selected={mode === m.id} title={m.hint}
                    className={`mode ${mode === m.id ? "on" : ""}`} onClick={() => setMode(m.id)}>{m.label}</button>
          ))}
          {mode === "duplicates" && ready && (
            <button type="button" className="btn small" onClick={scanDuplicates} disabled={busy}>
              {scanning ? "Scanning…" : "Scan whole repo"}
            </button>
          )}
          {configured.length > 1 && (
            <select className="provider" aria-label="LLM provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="">Default model</option>
              {configured.map((p) => <option key={p.provider} value={p.provider}>{p.provider} · {p.default_model}</option>)}
            </select>
          )}
        </div>
        <div className="input-row">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={2} maxLength={2000}
                    placeholder={ready ? `${current.hint}: ask about ${repo.name}…` : "Waiting for the repository to finish indexing…"}
                    disabled={!ready} aria-label="Your question" />
          <button className="btn primary" disabled={!ready || busy || input.trim().length < 3}>Send</button>
        </div>
      </form>
    </section>
  );
}
