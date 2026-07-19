import { useEffect, useState } from "react";
import { api } from "./api";

export default function Dashboard({ user, onOpenWorkspace, onLogout }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .dashboard()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-glyph">{"</>"}</span>
          <div>
            <h1>Dashboard</h1>
            <p className="tagline">Welcome back, {user.name}.</p>
          </div>
        </div>
        <button className="ghost" onClick={onLogout}>
          Log out
        </button>
      </header>

      <main className="dash-layout">
        <section className="panel">
          <h2>Account</h2>
          <div className="account-card">
            <div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div>
            <div>
              <p className="account-name">{user.name}</p>
              <p className="account-email">{user.email}</p>
            </div>
          </div>
          <button onClick={() => onOpenWorkspace(null)} style={{ marginTop: 16, width: "100%" }}>
            + New repo
          </button>
        </section>

        <section className="panel">
          <h2>Your repositories</h2>
          {error && <p className="status-error">{error}</p>}
          {!data && !error && <p className="text-dim">Loading…</p>}
          {data?.repos.length === 0 && <p className="text-dim">No repos indexed yet.</p>}
          <ul className="repo-list">
            {data?.repos.map((r) => (
              <li key={r.id}>
                <button className="repo-item" onClick={() => onOpenWorkspace(r)}>
                  <span className="repo-url">{r.url}</span>
                  <span className="repo-meta">
                    {r.num_files} files · {r.num_chunks} chunks
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Recent history</h2>
          {data?.history.length === 0 && <p className="text-dim">No questions asked yet.</p>}
          <div className="history">
            {data?.history.map((h) => (
              <article key={h.id} className="answer-card">
                <p className="question">
                  <span className="badge">{h.action_type}</span> {h.question}
                </p>
                <p className="plan">{h.repo_url}</p>
                <pre className="answer">{h.answer}</pre>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
