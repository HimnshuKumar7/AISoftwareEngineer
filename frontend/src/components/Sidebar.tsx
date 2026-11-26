import { FormEvent, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { ACTIVE_STATUSES, type Repo } from "../types";
import StatusBadge from "./StatusBadge";

interface Props {
  repos: Repo[];
  activeId?: string;
  onSelect: (id: string) => void;
  onChanged: () => void;
  onDeleted: (id: string) => void;
  onClose?: () => void;
}

export default function Sidebar({ repos, activeId, onSelect, onChanged, onDeleted, onClose }: Props) {
  const { user, logout } = useAuth();
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [showBranch, setShowBranch] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const repo = await api.addRepo(url.trim(), branch.trim() || undefined);
      setUrl(""); setBranch("");
      onChanged();
      onSelect(repo.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the repository.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(repo: Repo) {
    if (!window.confirm(`Delete ${repo.owner}/${repo.name} and its index and chat history?`)) return;
    try {
      await api.deleteRepo(repo.id);
      onDeleted(repo.id);
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function reindex(repo: Repo) {
    try { await api.reindex(repo.id); onChanged(); }
    catch (err) { window.alert(err instanceof ApiError ? err.message : "Re-index failed"); }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="brand"><span className="brand-mark">{"</>"}</span> AI Software Engineer</div>
        {onClose && <button className="icon-btn mobile-only" onClick={onClose} aria-label="Close menu">✕</button>}
      </div>

      <form className="add-repo" onSubmit={add}>
        <label className="sr-only" htmlFor="repo-url">GitHub repository URL</label>
        <input id="repo-url" placeholder="https://github.com/owner/repo" value={url}
               onChange={(e) => setUrl(e.target.value)} spellCheck={false} autoComplete="off" />
        {showBranch && (
          <input aria-label="Branch" placeholder="branch (optional)" value={branch}
                 onChange={(e) => setBranch(e.target.value)} spellCheck={false} />
        )}
        <div className="row">
          <button type="button" className="link-btn" onClick={() => setShowBranch((v) => !v)}>
            {showBranch ? "Default branch" : "Choose branch"}
          </button>
          <button className="btn primary" disabled={busy || url.trim().length < 10}>{busy ? "Adding…" : "Index repo"}</button>
        </div>
        {error && <div className="alert error small" role="alert">{error}</div>}
      </form>

      <div className="section-title">Repositories</div>
      <ul className="repo-list">
        {repos.length === 0 && <li className="empty">No repositories yet. Paste a public GitHub URL above to index one.</li>}
        {repos.map((r) => {
          const active = ACTIVE_STATUSES.includes(r.status);
          return (
            <li key={r.id} className={`repo ${r.id === activeId ? "selected" : ""}`}>
              <button className="repo-main" onClick={() => onSelect(r.id)}>
                <span className="repo-name">{r.owner}/<strong>{r.name}</strong></span>
                <span className="repo-meta">
                  <StatusBadge status={r.status} />
                  {r.status === "ready" && <span className="muted">{r.chunk_count.toLocaleString()} chunks</span>}
                </span>
                {active && (
                  <>
                    <span className="progress" role="progressbar" aria-valuenow={r.progress} aria-valuemin={0} aria-valuemax={100}>
                      <span style={{ width: `${Math.max(4, r.progress)}%` }} />
                    </span>
                    <span className="muted small">{r.status_message}</span>
                  </>
                )}
                {r.status === "failed" && <span className="small error-text">{r.status_message}</span>}
              </button>
              <div className="repo-actions">
                <button className="link-btn" disabled={active} onClick={() => reindex(r)}>Re-index</button>
                <button className="link-btn danger" disabled={active} onClick={() => remove(r)}>Delete</button>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="sidebar-foot">
        <span className="muted ellipsis" title={user?.email}>{user?.email}</span>
        <button className="link-btn" onClick={logout}>Sign out</button>
      </div>
    </aside>
  );
}
