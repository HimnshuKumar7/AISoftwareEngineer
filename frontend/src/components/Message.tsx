import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyCitations, parseCiteHref, resolveSource } from "../lib/citations";
import type { QueryResult, Source } from "../types";
import type { ActiveSource } from "./SourcePanel";

interface Props {
  result: QueryResult;
  onOpen: (a: ActiveSource) => void;
}

const MODE_LABEL: Record<string, string> = { qa: "Ask", explain: "Explain", optimize: "Optimize", duplicates: "Duplicates" };

export default function Message({ result, onOpen }: Props) {
  const [showPlan, setShowPlan] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const md = useMemo(() => linkifyCitations(result.answer), [result.answer]);

  const open = (s: Source, start = s.start_line, end = s.end_line) => onOpen({ source: s, start, end });
  const cited = result.sources.filter((s) => s.cited);

  return (
    <>
      <div className="msg user">
        <span className="tag">{MODE_LABEL[result.mode] ?? result.mode}</span>
        <p>{result.question}</p>
      </div>
      <div className="msg assistant">
        <div className="md">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            urlTransform={(u) => u}
            components={{
              a({ href, children }) {
                const ref = parseCiteHref(href);
                if (ref) {
                  const hit = resolveSource(result.sources, ref);
                  return (
                    <button className="cite" disabled={!hit} title={hit ? "Open source" : "Source not available"}
                            onClick={() => hit && open(hit.source, hit.start, hit.end)}>
                      {children}
                    </button>
                  );
                }
                if (href && /^https?:\/\//i.test(href)) return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                return <span>{children}</span>;
              },
            }}
          >
            {md}
          </ReactMarkdown>
        </div>

        {cited.length > 0 && (
          <div className="cites">
            <span className="muted small">Cited:</span>
            {result.citations.map((c, i) => {
              const hit = resolveSource(result.sources, { path: c.path, start: c.start_line, end: c.end_line });
              return (
                <button key={i} className="cite" disabled={!hit} onClick={() => hit && open(hit.source, hit.start, hit.end)}>
                  <code>{c.path}:{c.start_line}{c.end_line !== c.start_line ? `-${c.end_line}` : ""}</code>
                </button>
              );
            })}
          </div>
        )}

        <div className="meta">
          <button className="link-btn" onClick={() => setShowPlan((v) => !v)}>
            {showPlan ? "Hide" : "Show"} search plan ({result.sub_queries.length})
          </button>
          <button className="link-btn" onClick={() => setShowContext((v) => !v)}>
            {showContext ? "Hide" : "Show"} retrieved code ({result.sources.length})
          </button>
          <span className="muted small">
            {result.llm_provider}/{result.llm_model} · {(result.latency_ms / 1000).toFixed(1)}s
          </span>
        </div>
        {showPlan && (
          <ol className="plan">{result.sub_queries.map((q, i) => <li key={i}><code>{q}</code></li>)}</ol>
        )}
        {showContext && (
          <ul className="ctx-list">
            {result.sources.map((s) => (
              <li key={s.chunk_id}>
                <button className="ctx-item" onClick={() => open(s)}>
                  <span className="mono path">{s.path}:{s.start_line}-{s.end_line}</span>
                  <span className="muted small">{s.kind} {s.name} · score {s.score.toFixed(2)}{s.cited ? " · cited" : ""}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
