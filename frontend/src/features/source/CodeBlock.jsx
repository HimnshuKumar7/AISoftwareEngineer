import { forwardRef } from "react";
import { classNames } from "../../lib/format";
import styles from "./CodeBlock.module.css";

/**
 * Numbered code listing with an optional highlighted line range.
 * @param {{ code: string, startLine?: number, highlight?: { start: number, end: number }, className?: string }} props
 */
const CodeBlock = forwardRef(function CodeBlock({ code, startLine = 1, highlight, className, ...props }, ref) {
  const lines = code.split("\n");
  const gutterDigits = String(startLine + lines.length - 1).length;

  return (
    <pre className={classNames(styles.block, className)} ref={ref} {...props}>
      <code className={styles.lines} style={{ "--gutter-digits": gutterDigits }}>
        {lines.map((line, index) => {
          const number = startLine + index;
          const marked = highlight && number >= highlight.start && number <= highlight.end;
          return (
            <span key={number} className={classNames(styles.line, marked && styles.marked)} data-marked={marked || undefined}>
              <span className={styles.number}>{number}</span>
              <span className={styles.content}>{line || " "}</span>
            </span>
          );
        })}
      </code>
    </pre>
  );
});

export default CodeBlock;
