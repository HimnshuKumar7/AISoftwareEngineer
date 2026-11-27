import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import TextField from "../../components/ui/TextField";
import { useAuth } from "../../hooks/useAuth";
import { useDelayedFlag } from "../../hooks/useDelayedFlag";
import { SLOW_REQUEST_NOTICE_MS } from "../../lib/constants";
import PasswordField from "./PasswordField";
import styles from "./AuthForm.module.css";

const COPY = {
  login: {
    title: "Sign in",
    subtitle: "Continue to your code workspace.",
    submit: "Sign in",
    switchText: "New here?",
    switchLink: "Create an account",
    switchTo: "/register",
  },
  register: {
    title: "Create your account",
    subtitle: "Start exploring repositories with grounded answers.",
    submit: "Create account",
    switchText: "Already registered?",
    switchLink: "Sign in",
    switchTo: "/login",
  },
};

export default function AuthForm({ mode }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const slow = useDelayedFlag(busy, SLOW_REQUEST_NOTICE_MS);

  const isLogin = mode === "login";
  const copy = COPY[mode];

  const validate = () => {
    if (!email.trim() || !password) return "Please enter both your email and password.";
    if (!isLogin && password.length < 8) return "Password must be at least 8 characters.";
    return null;
  };

  async function handleSubmit(event) {
    event.preventDefault();
    const problem = validate();
    setError(problem);
    if (problem) return;

    setBusy(true);
    try {
      if (isLogin) await login(email.trim(), password);
      else await register(email.trim(), password, name.trim() || undefined);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Something went wrong. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} aria-labelledby="auth-title" noValidate>
      <header className={styles.header}>
        <h1 id="auth-title" className={styles.title}>
          {copy.title}
        </h1>
        <p className={styles.subtitle}>{copy.subtitle}</p>
      </header>

      {!isLogin && (
        <TextField
          label="Name"
          optional
          name="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
          enterKeyHint="next"
          maxLength={120}
        />
      )}
      <TextField
        label="Email"
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
      <PasswordField
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={isLogin ? 1 : 8}
        maxLength={72}
        autoComplete={isLogin ? "current-password" : "new-password"}
        hint={isLogin ? undefined : "At least 8 characters."}
      />

      {error && <Alert tone="error">{error}</Alert>}
      {slow && <Alert>Waking up the server. This can take up to a minute on the free tier.</Alert>}

      <Button type="submit" variant="primary" block disabled={busy}>
        {busy ? "Please wait…" : copy.submit}
      </Button>

      <p className={styles.switch}>
        {copy.switchText} <Link to={copy.switchTo}>{copy.switchLink}</Link>
      </p>
    </form>
  );
}
