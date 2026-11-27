import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { resolveSource } from "../../lib/citations";
import { classNames, formatLocation } from "../../lib/format";
import CitationButton from "./CitationButton";
import RetrievedSources from "./RetrievedSources";
import styles from "./AnswerFooter.module.css";

function Toggle({ open, onClick, children }) {
  return (
    <button type="button" className={classNames(styles.toggle, open && styles.open)} aria-expanded={open} onClick={onClick}>
      <ChevronRight aria-hidden="true" />
      {children}
    </button>
  );
}

/** Citations, the search plan, the retrieved code and model details for an answer. */
export default function AnswerFooter({ result, onOpenSource }) {
  const [showPlan, setShowPlan] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const hasCitations = result.sources.some((source) => source.cited);

  return (
    <>
      {hasCitations && (
        <div className={styles.citations}>
          <span className={styles.citationsLabel}>Cited</span>
          {result.citations.map((citation, index) => {
            const { path, start_line: start, end_line: end } = citation;
            return (
              <CitationButton
                key={index}
                hit={resolveSource(result.sources, { path, start, end })}
                onOpenSource={onOpenSource}
              >
                {formatLocation(path, start, end)}
              </CitationButton>
            );
          })}
        </div>
      )}

      <div className={styles.bar}>
        <Toggle open={showPlan} onClick={() => setShowPlan((value) => !value)}>
          Search plan ({result.sub_queries.length})
        </Toggle>
        <Toggle open={showSources} onClick={() => setShowSources((value) => !value)}>
          Retrieved code ({result.sources.length})
        </Toggle>
        <span className={styles.model}>
          <span>
            {result.llm_provider}/{result.llm_model}
          </span>
          <span>{(result.latency_ms / 1000).toFixed(1)}s</span>
        </span>
      </div>

      {showPlan && (
        <ol className={styles.plan}>
          {result.sub_queries.map((query, index) => (
            <li key={index}>
              <code>{query}</code>
            </li>
          ))}
        </ol>
      )}
      {showSources && <RetrievedSources sources={result.sources} onOpenSource={onOpenSource} />}
    </>
  );
}
