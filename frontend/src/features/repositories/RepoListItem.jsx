import ProgressBar from "../../components/ui/ProgressBar";
import { ACTIVE_STATUSES } from "../../lib/constants";
import { classNames, plural } from "../../lib/format";
import RepoStatusBadge from "./RepoStatusBadge";
import styles from "./RepoListItem.module.css";

export default function RepoListItem({ repo, selected, onSelect }) {
  const indexing = ACTIVE_STATUSES.includes(repo.status);

  return (
    <button
      type="button"
      className={classNames(styles.item, selected && styles.selected)}
      aria-current={selected ? "page" : undefined}
      onClick={() => onSelect(repo.id)}
    >
      <span className={styles.name} title={`${repo.owner}/${repo.name}`}>
        {repo.name}
      </span>
      <span className={styles.owner}>{repo.owner}</span>
      <span className={styles.meta}>
        <RepoStatusBadge status={repo.status} />
        {repo.status === "ready" && <span>{plural(repo.chunk_count, "chunk")}</span>}
      </span>
      {indexing && (
        <span className={styles.detail}>
          <ProgressBar value={repo.progress} label={`Indexing ${repo.name}`} />
          <span>{repo.status_message}</span>
        </span>
      )}
      {repo.status === "failed" && <span className={styles.failure}>{repo.status_message}</span>}
    </button>
  );
}
