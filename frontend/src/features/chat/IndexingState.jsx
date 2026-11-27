import { CircleAlert, Database } from "lucide-react";
import EmptyState from "../../components/ui/EmptyState";
import ProgressBar from "../../components/ui/ProgressBar";
import { ACTIVE_STATUSES } from "../../lib/constants";
import { classNames } from "../../lib/format";
import styles from "./IndexingState.module.css";

const STEPS = [
  { status: "cloning", label: "Clone" },
  { status: "parsing", label: "Parse" },
  { status: "embedding", label: "Embed" },
  { status: "indexing", label: "Index" },
];

/** Shown while a repository is not ready: pipeline progress, or the reason it failed. */
export default function IndexingState({ repo }) {
  if (!ACTIVE_STATUSES.includes(repo.status)) {
    return (
      <EmptyState icon={CircleAlert} title="Indexing failed">
        <p className={styles.failure}>{repo.status_message}</p>
        <p className={styles.note}>Use the re-index button at the top of this page to try again.</p>
      </EmptyState>
    );
  }

  const current = STEPS.findIndex((step) => step.status === repo.status); // -1 while queued

  return (
    <EmptyState icon={Database} title="Indexing in progress" description={repo.status_message || "Working…"}>
      <div className={styles.progress}>
        <ProgressBar value={repo.progress} label="Indexing progress" />
        <ol className={styles.steps}>
          {STEPS.map((step, index) => (
            <li
              key={step.status}
              className={classNames(index < current && styles.done, index === current && styles.current)}
              aria-current={index === current ? "step" : undefined}
            >
              {step.label}
            </li>
          ))}
        </ol>
      </div>
      <p className={styles.note}>You can ask questions as soon as it is ready.</p>
    </EmptyState>
  );
}
