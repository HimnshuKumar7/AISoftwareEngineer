import RepoListItem from "./RepoListItem";
import styles from "./RepoList.module.css";

export default function RepoList({ repos, activeId, onSelect }) {
  if (repos.length === 0) {
    return <p className={styles.empty}>No repositories yet. Paste a public GitHub URL above to index one.</p>;
  }
  return (
    <ul className={styles.list}>
      {repos.map((repo) => (
        <li key={repo.id}>
          <RepoListItem repo={repo} selected={repo.id === activeId} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  );
}
