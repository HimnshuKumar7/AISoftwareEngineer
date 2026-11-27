import { useEffect, useRef } from "react";
import { Check, Copy, ExternalLink, X } from "lucide-react";
import Button from "../../components/ui/Button";
import IconButton from "../../components/ui/IconButton";
import { useCopyToClipboard } from "../../hooks/useCopyToClipboard";
import { useEscapeKey } from "../../hooks/useEscapeKey";
import { githubBlobUrl } from "../../lib/citations";
import { splitPath } from "../../lib/format";
import CodeBlock from "./CodeBlock";
import styles from "./SourcePanel.module.css";

/** Right-hand viewer for one retrieved source, with the cited lines highlighted. */
export default function SourcePanel({ active, repo, onClose }) {
  const { source, start, end } = active;
  const { copied, copy } = useCopyToClipboard();
  const codeRef = useRef(null);
  const { directory, file } = splitPath(source.path);
  const narrowed = start !== source.start_line || end !== source.end_line;

  useEscapeKey(true, onClose);

  // Bring the first highlighted line into view inside the code area only.
  useEffect(() => {
    const container = codeRef.current;
    const line = container?.querySelector("[data-marked]");
    if (!line) return;
    const offset = line.getBoundingClientRect().top - container.getBoundingClientRect().top;
    container.scrollTop += offset - container.clientHeight / 4;
    container.scrollLeft = 0;
  }, [source, start, end]);

  return (
    <aside className={styles.panel} aria-label="Source viewer">
      <header className={styles.header}>
        <div className={styles.heading}>
          <h2 className={styles.file} title={source.path}>
            {file}
          </h2>
          <p className={styles.directory} title={source.path}>
            {directory || "Repository root"}
          </p>
        </div>
        <IconButton icon={X} label="Close source viewer" onClick={onClose} />
      </header>

      <div className={styles.toolbar}>
        <dl className={styles.details}>
          <div>
            <dt>
              {source.language} {source.kind}
            </dt>
            <dd className={styles.mono}>{source.name}</dd>
          </div>
          <div>
            <dt>Lines</dt>
            <dd>
              {source.start_line}–{source.end_line}
            </dd>
          </div>
          {narrowed && (
            <div>
              <dt>Cited</dt>
              <dd className={styles.cited}>
                {start}–{end}
              </dd>
            </div>
          )}
        </dl>
        <div className={styles.actions}>
          <Button
            size="sm"
            icon={ExternalLink}
            href={githubBlobUrl(repo.owner, repo.name, repo.commit_sha, source.path, start, end)}
            target="_blank"
            rel="noopener noreferrer"
          >
            View on GitHub
          </Button>
          <Button size="sm" icon={copied ? Check : Copy} onClick={() => copy(source.code)}>
            {copied ? "Copied" : "Copy code"}
          </Button>
        </div>
      </div>

      <CodeBlock
        ref={codeRef}
        code={source.code}
        startLine={source.start_line}
        highlight={{ start, end }}
        className={styles.code}
        tabIndex={0}
      />

      {source.also_at?.length > 0 && (
        <footer className={styles.footer}>
          Identical code also at <code>{source.also_at.join(", ")}</code>
        </footer>
      )}
    </aside>
  );
}
