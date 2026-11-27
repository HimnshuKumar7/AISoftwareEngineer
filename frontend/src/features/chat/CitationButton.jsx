import styles from "./CitationButton.module.css";

/** A file-and-line reference that opens the source viewer. `hit` is the result of `resolveSource`. */
export default function CitationButton({ hit, onOpenSource, children }) {
  return (
    <button
      type="button"
      className={styles.citation}
      disabled={!hit}
      title={hit ? "Open source" : "Source not available"}
      onClick={() => hit && onOpenSource(hit)}
    >
      {children}
    </button>
  );
}
