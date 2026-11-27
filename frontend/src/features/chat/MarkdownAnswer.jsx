import { useMemo } from "react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyCitations, parseCiteHref, resolveSource } from "../../lib/citations";
import CitationButton from "./CitationButton";
import styles from "./MarkdownAnswer.module.css";

const keepCitations = (url) => (url.startsWith("cite:") ? url : defaultUrlTransform(url));

/** Model output rendered as markdown (no raw HTML), with citations turned into buttons. */
export default function MarkdownAnswer({ markdown, sources, onOpenSource }) {
  const linked = useMemo(() => linkifyCitations(markdown), [markdown]);

  return (
    <div className={styles.markdown}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={keepCitations}
        components={{
          table({ children }) {
            return (
              <div className={styles.tableWrapper} tabIndex={0} role="region" aria-label="Data table">
                <table>{children}</table>
              </div>
            );
          },
          a({ href, children }) {
            const ref = parseCiteHref(href);
            if (ref) {
              return (
                <CitationButton hit={resolveSource(sources, ref)} onOpenSource={onOpenSource}>
                  {children}
                </CitationButton>
              );
            }
            if (href && /^https?:\/\//i.test(href)) {
              return (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              );
            }
            return <span>{children}</span>;
          },
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}
