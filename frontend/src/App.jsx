import { Navigate, Route, Routes } from "react-router-dom";
import { API_CONFIGURED } from "./api/client";
import ProtectedRoute from "./components/ProtectedRoute";
import Alert from "./components/ui/Alert";
import { useAuth } from "./hooks/useAuth";
import AuthPage from "./pages/AuthPage";
import WorkspacePage from "./pages/WorkspacePage";

export default function App() {
  const { user, loading } = useAuth();

  /** Signed-in users skip the sign-in and register screens. */
  const guestOnly = (mode) =>
    !loading && user ? <Navigate to="/app" replace /> : <AuthPage mode={mode} />;

  const workspace = (
    <ProtectedRoute>
      <WorkspacePage />
    </ProtectedRoute>
  );

  return (
    <div className="app-shell">
      {!API_CONFIGURED && (
        <Alert tone="error" banner>
          VITE_API_URL is not set, so the app cannot reach the backend. Add it in Vercel project
          settings and redeploy.
        </Alert>
      )}
      <div className="app-content">
        <Routes>
          <Route path="/login" element={guestOnly("login")} />
          <Route path="/register" element={guestOnly("register")} />
          <Route path="/app" element={workspace} />
          <Route path="/app/:repoId" element={workspace} />
          <Route path="*" element={<Navigate to={user ? "/app" : "/login"} replace />} />
        </Routes>
      </div>
    </div>
  );
}
