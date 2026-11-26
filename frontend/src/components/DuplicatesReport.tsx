import type { DuplicateReport } from "../types";

export default function DuplicatesReport({ report }: { report: DuplicateReport }) {
  return (
    <div className="msg assistant">
      <p>
        <strong>Duplicate scan</strong>: {report.group_count} group{report.group_count === 1 ? "" : "s"} found across{" "}
        {report.scanned_chunks.toLocaleString()} functions/methods
        {report.scan_truncated ? " (scan limited to the first 8,000)" : ""}. Exact copies are matched by content;
        near-duplicates by MiniLM embedding similarity (≥ {report.threshold}) confirmed by token overlap.
      </p>
      {report.groups.length === 0 && <p className="muted">No duplicated functions detected.</p>}
      {report.groups.map((g, i) => (
        <details key={i} className="dup-group" open={i < 2}>
          <summary>
            <span className={`badge ${g.exact ? "badge-failed" : "badge-parsing"}`}>{g.exact ? "exact" : "near"}</span>{" "}
            {g.size} locations · token overlap {(g.min_lexical_similarity * 100).toFixed(0)}%
          </summary>
          {g.locations.map((l) => (
            <div key={l.chunk_id} className="dup-loc">
              <div className="mono path">{l.path}:{l.start_line}-{l.end_line} <span className="muted">{l.name}</span></div>
              <pre className="code small"><code>{l.code_preview}</code></pre>
            </div>
          ))}
        </details>
      ))}
    </div>
  );
}
