import { useState } from "react";
import { githubBlobUrl } from "../lib/citations";
import type { Repo, Source } from "../types";

export interface ActiveSource { source: Source; start: number; end: number }

export default function SourcePanel({ active, repo, onClose }: { active: ActiveSource; repo: Repo; onClose: () => void }) {
  const { source, start, end } = active;
  const [copied, setCopied] = useState(false);
  const lines = source.code.split("\n");
  const width = String(source.end_line).length;

  async function copy() {
    try { await navigator.clipboard.writeText(source.code); setCopied(true); setTimeout(() => setCopied(false), 1500); }
    catch { /* clipboard unavailable */ }
  }

  return (
    <aside className="source-panel" aria-label="Source viewer">
      <header>
        <div>
          <div className="mono path">{source.path}</div>
          <div className="muted small">
            {source.language} {source.kind} <span className="mono">{source.name}</span> · lines {source.start_line}–{source.end_line}
            {start !== source.start_line || end !== source.end_line ? ` · cited ${start}–${end}` : ""}
          </div>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close source viewer">✕</button>
      </header>
      <div className="source-actions">
        <a className="btn small" href={githubBlobUrl(repo.owner, repo.name, repo.commit_sha, source.path, start, end)}
           target="_blank" rel="noopener noreferrer">View on GitHub ↗</a>
        <button className="btn small" onClick={copy}>{copied ? "Copied" : "Copy code"}</button>
      </div>
      <pre className="code" tabIndex={0}>
        {lines.map((ln, i) => {
          const n = source.start_line + i;
          const hl = n >= start && n <= end;
          return (
            <div key={n} className={`code-line ${hl ? "hl" : ""}`}>
              <span className="ln">{String(n).padStart(width, " ")}</span>
              <span className="lc">{ln || " "}</span>
            </div>
          );
        })}
      </pre>
      {source.also_at && source.also_at.length > 0 && (
        <div className="muted small pad">Identical code also at: <span className="mono">{source.also_at.join(", ")}</span></div>
      )}
    </aside>
  );
}
