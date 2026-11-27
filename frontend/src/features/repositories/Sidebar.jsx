import { LogOut, X } from "lucide-react";
import Brand from "../../components/ui/Brand";
import IconButton from "../../components/ui/IconButton";
import { useAuth } from "../../hooks/useAuth";
import AddRepoForm from "./AddRepoForm";
import RepoList from "./RepoList";
import styles from "./Sidebar.module.css";

export default function Sidebar({ repos, activeId, onSelect, onAdded, onClose }) {
  const { user, logout } = useAuth();

  return (
    <aside className={styles.sidebar}>
      <header className={styles.header}>
        <Brand />
        <IconButton icon={X} label="Close menu" className={styles.close} onClick={onClose} />
      </header>

      <AddRepoForm onAdded={onAdded} />

      <nav className={styles.nav} aria-labelledby="repo-list-title">
        <h2 id="repo-list-title" className={styles.title}>
          Repositories
        </h2>
        <RepoList repos={repos} activeId={activeId} onSelect={onSelect} />
      </nav>

      <footer className={styles.account}>
        <span className={styles.email} title={user?.email}>
          {user?.email}
        </span>
        <IconButton icon={LogOut} label="Sign out" onClick={logout} />
      </footer>
    </aside>
  );
}
