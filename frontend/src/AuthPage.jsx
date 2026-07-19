import { useState } from "react";
import { api, saveToken } from "./api";

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data =
        mode === "signup"
          ? await api.signup(name, email, password)
          : await api.login(email, password);
      saveToken(data.access_token);
      onAuthenticated(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="brand center">
          <span className="brand-glyph">{"</>"}</span>
          <div>
            <h1>repo:// AI Software Engineer</h1>
            <p className="tagline">Sign in to index repos and keep your history.</p>
          </div>
        </div>

        <div className="toggle">
          <button
            type="button"
            className={mode === "signin" ? "toggle-btn active" : "toggle-btn"}
            onClick={() => setMode("signin")}
          >
            Sign in
          </button>
          <button
            type="button"
            className={mode === "signup" ? "toggle-btn active" : "toggle-btn"}
            onClick={() => setMode("signup")}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === "signup" && (
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>

          {error && <p className="status-error">{error}</p>}

          <button type="submit" disabled={loading}>
            {loading
              ? mode === "signup"
                ? "Creating account…"
                : "Signing in…"
              : mode === "signup"
              ? "Create account"
              : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
