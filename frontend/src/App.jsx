import { useEffect, useState } from "react";
import { api, getToken, clearToken } from "./api";
import AuthPage from "./AuthPage";
import Dashboard from "./Dashboard";
import Workspace from "./Workspace";

export default function App() {
  const [status, setStatus] = useState("loading"); // loading | signedOut | dashboard | workspace
  const [user, setUser] = useState(null);
  const [activeRepo, setActiveRepo] = useState(null);

  useEffect(() => {
    if (!getToken()) {
      setStatus("signedOut");
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        setStatus("dashboard");
      })
      .catch(() => {
        clearToken();
        setStatus("signedOut");
      });
  }, []);

  function handleAuthenticated(u) {
    setUser(u);
    setStatus("dashboard");
  }

  function handleLogout() {
    clearToken();
    setUser(null);
    setActiveRepo(null);
    setStatus("signedOut");
  }

  function openWorkspace(repo) {
    setActiveRepo(repo);
    setStatus("workspace");
  }

  if (status === "loading") return null;

  if (status === "signedOut") {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  if (status === "workspace") {
    return <Workspace initialRepo={activeRepo} onBackToDashboard={() => setStatus("dashboard")} />;
  }

  return <Dashboard user={user} onOpenWorkspace={openWorkspace} onLogout={handleLogout} />;
}
