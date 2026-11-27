import { MessagesSquare } from "lucide-react";
import EmptyState from "../../components/ui/EmptyState";
import { getMode } from "../../lib/constants";
import styles from "./EmptyChat.module.css";

export default function EmptyChat({ repoName, mode, onPickExample }) {
  return (
    <EmptyState
      icon={MessagesSquare}
      title={`Ask anything about ${repoName}`}
      description="Answers are grounded in retrieved code and cite file paths and line numbers."
    >
      <ul className={styles.examples}>
        {getMode(mode).examples.map((example) => (
          <li key={example}>
            <button type="button" onClick={() => onPickExample(example)}>
              {example}
            </button>
          </li>
        ))}
      </ul>
    </EmptyState>
  );
}
