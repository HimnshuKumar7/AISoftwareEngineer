import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { reposApi } from "../api/repos";
import { ACTIVE_STATUSES, REPO_POLL_INTERVAL_MS } from "../lib/constants";

/** The signed-in user's repositories, refreshed automatically while any of them is indexing. */
export function useRepositories() {
  const [repos, setRepos] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setRepos(await reposApi.list());
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load repositories"));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const isIndexing = repos.some((repo) => ACTIVE_STATUSES.includes(repo.status));
  useEffect(() => {
    if (!isIndexing) return undefined;
    const timer = setInterval(() => void refresh(), REPO_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isIndexing, refresh]);

  /** Show a created or updated repository immediately, ahead of the next refresh. */
  const upsert = useCallback((repo) => {
    setRepos((list) =>
      list.some((item) => item.id === repo.id)
        ? list.map((item) => (item.id === repo.id ? repo : item))
        : [repo, ...list],
    );
  }, []);

  const remove = useCallback((id) => {
    setRepos((list) => list.filter((item) => item.id !== id));
  }, []);

  return { repos, loaded, error, refresh, upsert, remove };
}
