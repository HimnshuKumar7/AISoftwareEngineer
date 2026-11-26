import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import Chat from "../components/Chat";
import Sidebar from "../components/Sidebar";
import SourcePanel, { type ActiveSource } from "../components/SourcePanel";
import { ACTIVE_STATUSES, type Repo } from "../types";

export default function Workspace() {
  const { repoId } = useParams();
  const nav = useNavigate();
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [active, setActive] = useState<ActiveSource | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRepos(await api.listRepos());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load repositories");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Poll only while something is indexing.
  const anyActive = useMemo(() => repos.some((r) => ACTIVE_STATUSES.includes(r.status)), [repos]);
  useEffect(() => {
    if (!anyActive) return;
    const t = setInterval(() => void refresh(), 2500);
    return () => clearInterval(t);
  }, [anyActive, refresh]);

  const repo = repos.find((r) => r.id === repoId);
  useEffect(() => { setActive(null); }, [repoId]);
  useEffect(() => {
    if (loaded && !repoId && repos.length > 0) nav(`/app/${repos[0].id}`, { replace: true });
  }, [loaded, repoId, repos, nav]);

  const select = (id: string) => { setMenu(false); nav(`/app/${id}`); };

  return (
    <div className={`workspace ${active ? "with-source" : ""}`}>
      <div className={`sidebar-wrap ${menu ? "open" : ""}`}>
        <Sidebar repos={repos} activeId={repoId} onSelect={select} onChanged={refresh}
                 onDeleted={(id) => { void refresh(); if (id === repoId) nav("/app", { replace: true }); }}
                 onClose={() => setMenu(false)} />
      </div>
      {menu && <div className="scrim" onClick={() => setMenu(false)} />}

      <main className="main">
        <button className="menu-btn mobile-only" onClick={() => setMenu(true)} aria-label="Open repositories">☰ Repositories</button>
        {error && <div className="alert error">{error}</div>}
        {!loaded ? (
          <div className="center-screen"><div className="spinner" /></div>
        ) : repo ? (
          <Chat repo={repo} onOpenSource={setActive} />
        ) : (
          <div className="empty-state big">
            <h2>Welcome</h2>
            <p className="muted">Paste a public GitHub repository URL in the sidebar to build a searchable code index,
              then ask questions, get explanations, find duplicates and optimization ideas, all with file and line citations.</p>
          </div>
        )}
      </main>

      {active && repo && <SourcePanel active={active} repo={repo} onClose={() => setActive(null)} />}
    </div>
  );
}
