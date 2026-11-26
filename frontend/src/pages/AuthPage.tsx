import { FormEvent, useEffect, useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const isLogin = mode === "login";

  const headingId = useId();
  const nameId = useId();
  const emailId = useId();
  const passwordId = useId();
  const passwordHintId = useId();

  useEffect(() => {
    setError(null);
    setShowPassword(false);
  }, [mode]);

  // Free-tier hosts sleep when idle; tell the user why the first request is slow.
  useEffect(() => {
    if (!busy) { setSlow(false); return; }
    const t = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(t);
  }, [busy]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError("Please enter both your email and password.");
      return;
    }
    if (!isLogin && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
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
      <form className="auth-card" onSubmit={onSubmit} aria-labelledby={headingId} noValidate>
        <header className="auth-header">
          <div className="brand">
            <span className="brand-mark">{"</>"}</span>
            <span>AI Software Engineer</span>
          </div>
          <p className="auth-tagline">
            Ask questions about any public GitHub repository, grounded in its real code.
          </p>
        </header>

        <div className="auth-intro">
          <h1 id={headingId}>{isLogin ? "Sign in" : "Create your account"}</h1>
          <p className="auth-heading-copy">
            {isLogin ? "Continue to your code workspace." : "Start exploring repositories with grounded answers."}
          </p>
        </div>

        <div className="auth-fields">
          {!isLogin && (
            <div className="field">
              <label htmlFor={nameId}>
                Name <span className="muted">(optional)</span>
              </label>
              <input
                id={nameId}
                name="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                enterKeyHint="next"
                maxLength={120}
              />
            </div>
          )}

          <div className="field">
            <label htmlFor={emailId}>Email</label>
            <input
              id={emailId}
              name="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              enterKeyHint="next"
            />
          </div>

          <div className="field">
            <label htmlFor={passwordId}>Password</label>
            <div className="password-wrap">
              <input
                id={passwordId}
                name="password"
                type={showPassword ? "text" : "password"}
                required
                minLength={isLogin ? 1 : 8}
                maxLength={72}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={isLogin ? "current-password" : "new-password"}
                aria-describedby={!isLogin ? passwordHintId : undefined}
                enterKeyHint="done"
              />
              <button
                type="button"
                className="password-toggle"
                aria-pressed={showPassword}
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {!isLogin && <p id={passwordHintId} className="hint">At least 8 characters.</p>}
          </div>
        </div>

        {error && <div className="alert error" role="alert" aria-live="polite">{error}</div>}
        {slow && <div className="alert info" role="status">Waking up the server. This can take up to a minute on the free tier…</div>}

        <button type="submit" className="btn primary block" disabled={busy}>
          {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
        </button>

        <p className="switch">
          {isLogin ? <>New here? <Link to="/register">Create an account</Link></> : <>Already registered? <Link to="/login">Sign in</Link></>}
        </p>
      </form>
    </main>
  );
}
