import { ChevronRight } from "lucide-react";
import Badge from "../../components/ui/Badge";
import { formatLocation, plural } from "../../lib/format";
import styles from "./DuplicatesReport.module.css";

export default function DuplicatesReport({ report }) {
  return (
    <article className={styles.report}>
      <header className={styles.header}>
        <h3 className={styles.title}>Duplicate scan</h3>
        <p>
          {plural(report.group_count, "group")} found across {report.scanned_chunks.toLocaleString()}{" "}
          functions and methods
          {report.scan_truncated ? " (scan limited to the first 8,000)" : ""}.
        </p>
        <p className={styles.method}>
          Exact copies are matched by content. Near-duplicates are matched by MiniLM embedding similarity
          (at least {report.threshold}) and confirmed by token overlap.
        </p>
      </header>

      {report.groups.length === 0 && <p className={styles.none}>No duplicated functions detected.</p>}

      {report.groups.map((group, index) => (
        <details key={index} className={styles.group} open={index < 2}>
          <summary className={styles.summary}>
            <ChevronRight className={styles.chevron} aria-hidden="true" />
            <Badge tone={group.exact ? "danger" : "warning"}>{group.exact ? "Exact" : "Near"}</Badge>
            <span className={styles.size}>{plural(group.size, "location")}</span>
            <span className={styles.overlap}>
              {(group.min_lexical_similarity * 100).toFixed(0)}% token overlap
            </span>
          </summary>
          <ul className={styles.locations}>
            {group.locations.map((location) => (
              <li key={location.chunk_id}>
                <div className={styles.location}>
                  <code>{formatLocation(location.path, location.start_line, location.end_line)}</code>
                  <span>{location.name}</span>
                </div>
                <pre className={styles.preview} tabIndex={0}>
                  <code>{location.code_preview}</code>
                </pre>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </article>
  );
}
