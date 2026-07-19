import { useState } from "react";
import { api } from "./api";

const QUICK_ACTIONS = [
  { key: "docs", label: "Generate docs", endpoint: "/api/repos/docs" },
  { key: "tests", label: "Generate unit tests", endpoint: "/api/repos/tests" },
  { key: "duplicates", label: "Find duplicate code", endpoint: "/api/repos/duplicates" },
  { key: "optimize", label: "Suggest optimizations", endpoint: "/api/repos/optimize" },
];

const STAGES = ["Planner", "Code Search", "Reasoner", "Final Answer"];

export default function Workspace({ initialRepo, onBackToDashboard }) {
  const [repoUrl, setRepoUrl] = useState(initialRepo?.url || "");
  const [repoId, setRepoId] = useState(initialRepo?.id || null);
  const [indexing, setIndexing] = useState(false);
  const [indexInfo, setIndexInfo] = useState(
    initialRepo
      ? { repo_id: initialRepo.id, num_files: initialRepo.num_files, num_chunks: initialRepo.num_chunks }
      : null
  );
  const [error, setError] = useState("");

  const [question, setQuestion] = useState("");
  const [filePath, setFilePath] = useState("");
  const [thinking, setThinking] = useState(false);
  const [activeStage, setActiveStage] = useState(-1);
  const [history, setHistory] = useState([]);

  async function handleIndex(e) {
    e.preventDefault();
    setError("");
    setIndexing(true);
    setIndexInfo(null);
    setRepoId(null);
    try {
      const data = await api.indexRepo(repoUrl);
      setRepoId(data.repo_id);
      setIndexInfo(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIndexing(false);
    }
  }

  async function runQuery(fn) {
    setThinking(true);
    setError("");
    setActiveStage(0);
    const stepper = setInterval(() => {
      setActiveStage((s) => (s < STAGES.length - 1 ? s + 1 : s));
    }, 700);
    try {
      const data = await fn();
      setHistory((h) => [data, ...h]);
    } catch (err) {
      setError(err.message);
    } finally {
      clearInterval(stepper);
      setActiveStage(-1);
      setThinking(false);
    }
  }

  function handleAsk(e) {
    e.preventDefault();
    if (!question.trim() || !repoId) return;
    const q = question;
    setQuestion("");
    runQuery(async () => ({ question: q, ...(await api.ask(repoId, q)) }));
  }

  function handleQuickAction(action) {
    if (!repoId || !filePath.trim()) return;
    runQuery(async () => ({
      question: `[${action.label}] ${filePath}`,
      ...(await api.fileAction(action.endpoint, repoId, filePath)),
    }));
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-glyph">{"</>"}</span>
          <div>
            <h1>repo:// AI Software Engineer</h1>
            <p className="tagline">Clone a repo. Ask anything. Watch the graph think.</p>
          </div>
        </div>
        <div className="header-right">
          <div className="pipeline">
            {STAGES.map((stage, i) => (
              <div
                key={stage}
                className={`pipeline-node ${activeStage === i ? "active" : ""} ${
                  activeStage > i ? "done" : ""
                }`}
              >
                <span className="dot" />
                <span className="label">{stage}</span>
                {i < STAGES.length - 1 && <span className="wire" />}
              </div>
            ))}
          </div>
          <button className="ghost" onClick={onBackToDashboard}>
            ← Dashboard
          </button>
        </div>
      </header>

      <main className="layout">
        <section className="panel">
          <h2>1. Index a repository</h2>
          <form onSubmit={handleIndex} className="row">
            <input
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              required
            />
            <button type="submit" disabled={indexing}>
              {indexing ? "Cloning + embedding…" : "Index repo"}
            </button>
          </form>
          {indexInfo && (
            <p className="status-ok">
              Indexed {indexInfo.num_files} files → {indexInfo.num_chunks} chunks.
              repo_id: <code>{indexInfo.repo_id}</code>
            </p>
          )}

          <h2>2. Quick actions</h2>
          <input
            className="file-input"
            placeholder="path/to/file.py"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
          />
          <div className="actions">
            {QUICK_ACTIONS.map((a) => (
              <button
                key={a.key}
                disabled={!repoId || thinking}
                onClick={() => handleQuickAction(a)}
                className="ghost"
              >
                {a.label}
              </button>
            ))}
          </div>

          {error && <p className="status-error">{error}</p>}
        </section>

        <section className="panel chat">
          <h2>3. Ask about the codebase</h2>
          <form onSubmit={handleAsk} className="row">
            <input
              placeholder={repoId ? "Where is JWT implemented?" : "Index a repo first…"}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={!repoId}
            />
            <button type="submit" disabled={!repoId || thinking}>
              {thinking ? "Thinking…" : "Ask"}
            </button>
          </form>

          <div className="history">
            {history.map((item, idx) => (
              <article key={idx} className="answer-card">
                <p className="question">{item.question}</p>
                {item.plan?.length > 0 && <p className="plan">plan: {item.plan.join(" · ")}</p>}
                <pre className="answer">{item.answer}</pre>
                {item.sources?.length > 0 && (
                  <details>
                    <summary>{item.sources.length} source chunk(s)</summary>
                    {item.sources.map((s, i) => (
                      <div key={i} className="source">
                        <span className="source-path">
                          {s.file_path}:{s.start_line}-{s.end_line}
                          {s.symbol ? ` (${s.symbol})` : ""}
                        </span>
                        <pre>{s.snippet}</pre>
                      </div>
                    ))}
                  </details>
                )}
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
