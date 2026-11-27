import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { FolderGit2, SearchX } from "lucide-react";
import Alert from "../components/ui/Alert";
import EmptyState from "../components/ui/EmptyState";
import Spinner from "../components/ui/Spinner";
import ChatPanel from "../features/chat/ChatPanel";
import Sidebar from "../features/repositories/Sidebar";
import SourcePanel from "../features/source/SourcePanel";
import MainHeader from "../features/workspace/MainHeader";
import { useEscapeKey } from "../hooks/useEscapeKey";
import { useProviders } from "../hooks/useProviders";
import { useRepositories } from "../hooks/useRepositories";
import { classNames } from "../lib/format";
import styles from "./WorkspacePage.module.css";

export default function WorkspacePage() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const { repos, loaded, error, refresh, upsert, remove } = useRepositories();
  const providers = useProviders();
  const [menuOpen, setMenuOpen] = useState(false);
  const [openSource, setOpenSource] = useState(null);
  // Mode and provider are preferences, so they survive switching repositories.
  const [mode, setMode] = useState("qa");
  const [provider, setProvider] = useState("");

  const repo = repos.find((item) => item.id === repoId);
  // A source belongs to one repository; it is ignored as soon as another one is open.
  const activeSource = repo && openSource?.repoId === repo.id ? openSource : null;

  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const openMenu = useCallback(() => setMenuOpen(true), []);
  const closeSource = useCallback(() => setOpenSource(null), []);
  useEscapeKey(menuOpen, closeMenu);

  useEffect(() => {
    setOpenSource(null);
  }, [repoId]);

  useEffect(() => {
    if (loaded && !repoId && repos.length > 0) navigate(`/app/${repos[0].id}`, { replace: true });
  }, [loaded, repoId, repos, navigate]);

  const selectRepo = (id) => {
    closeMenu();
    navigate(`/app/${id}`);
  };

  const handleAdded = (added) => {
    upsert(added);
    selectRepo(added.id);
    void refresh();
  };

  const handleUpdated = (updated) => {
    upsert(updated);
    void refresh();
  };

  const handleDeleted = (id) => {
    remove(id);
    navigate("/app", { replace: true });
    void refresh();
  };

  let content;
  if (!loaded) {
    content = <Spinner fill />;
  } else if (repo) {
    content = (
      <ChatPanel
        key={repo.id}
        repo={repo}
        providers={providers}
        mode={mode}
        onModeChange={setMode}
        provider={provider}
        onProviderChange={setProvider}
        onOpenSource={(source) => setOpenSource({ ...source, repoId: repo.id })}
        onOpenMenu={openMenu}
        onRepoUpdated={handleUpdated}
        onRepoDeleted={handleDeleted}
      />
    );
  } else {
    const missing = Boolean(repoId) && repos.length > 0;
    content = (
      <>
        <MainHeader onOpenMenu={openMenu}>
          <h1 className={styles.pageTitle}>Workspace</h1>
        </MainHeader>
        {missing ? (
          <EmptyState
            icon={SearchX}
            title="Repository not found"
            description="It may have been deleted. Choose another repository from the list."
          />
        ) : (
          <EmptyState
            icon={FolderGit2}
            title="Add your first repository"
            description="Paste a public GitHub repository URL in the sidebar to build a searchable code index. Then ask questions, get explanations, and find duplicates and optimization ideas, all with file and line citations."
          />
        )}
      </>
    );
  }

  return (
    <div className={classNames(styles.workspace, activeSource && styles.withSource)}>
      <div className={classNames(styles.sidebar, menuOpen && styles.open)}>
        <Sidebar repos={repos} activeId={repoId} onSelect={selectRepo} onAdded={handleAdded} onClose={closeMenu} />
      </div>
      {menuOpen && <div className={styles.scrim} onClick={closeMenu} />}

      <main className={styles.main}>
        {error && (
          <Alert tone="error" banner>
            {error}
          </Alert>
        )}
        {content}
      </main>

      {activeSource && (
        <div className={styles.source}>
          <SourcePanel active={activeSource} repo={repo} onClose={closeSource} />
        </div>
      )}
    </div>
  );
}
