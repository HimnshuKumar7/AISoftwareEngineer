import { formatLocation } from "../../lib/format";
import styles from "./RetrievedSources.module.css";

export default function RetrievedSources({ sources, onOpenSource }) {
  return (
    <ul className={styles.list}>
      {sources.map((source) => (
        <li key={source.chunk_id}>
          <button
            type="button"
            className={styles.source}
            onClick={() => onOpenSource({ source, start: source.start_line, end: source.end_line })}
          >
            <code className={styles.path}>{formatLocation(source.path, source.start_line, source.end_line)}</code>
            <span className={styles.meta}>
              <span>
                {source.kind} {source.name}
              </span>
              <span>score {source.score.toFixed(2)}</span>
              {source.cited && <span className={styles.cited}>Cited</span>}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
