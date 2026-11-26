import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const isLogin = mode === "login";

  useEffect(() => { setError(null); }, [mode]);

  // Free-tier hosts sleep when idle; tell the user why the first request is slow.
  useEffect(() => {
    if (!busy) { setSlow(false); return; }
    const t = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(t);
  }, [busy]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isLogin) await login(email.trim(), password);
      else await register(email.trim(), password, name.trim() || undefined);
      nav("/app", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-wrap">
      <form className="auth-card" onSubmit={onSubmit} noValidate>
        <div className="brand"><span className="brand-mark">{"</>"}</span> AI Software Engineer</div>
        <p className="muted">Ask questions about any public GitHub repository, grounded in its real code.</p>
        <h1>{isLogin ? "Sign in" : "Create your account"}</h1>

        {!isLogin && (
          <label>Name <span className="muted">(optional)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={120} />
          </label>
        )}
        <label>Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </label>
        <label>Password
          <input type="password" required minLength={isLogin ? 1 : 8} maxLength={72} value={password}
                 onChange={(e) => setPassword(e.target.value)}
                 autoComplete={isLogin ? "current-password" : "new-password"} />
        </label>
        {!isLogin && <p className="hint">At least 8 characters.</p>}

        {error && <div className="alert error" role="alert">{error}</div>}
        {slow && <div className="alert info">Waking up the server. This can take up to a minute on the free tier…</div>}

        <button className="btn primary block" disabled={busy || !email || !password}>
          {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
        </button>
        <p className="switch">
          {isLogin ? <>New here? <Link to="/register">Create an account</Link></> : <>Already registered? <Link to="/login">Sign in</Link></>}
        </p>
      </form>
    </main>
  );
}
