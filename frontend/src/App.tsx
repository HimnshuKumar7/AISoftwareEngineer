import { Navigate, Route, Routes } from "react-router-dom";
import { API_CONFIGURED } from "./api";
import { useAuth } from "./auth";
import AuthPage from "./pages/AuthPage";
import Workspace from "./pages/Workspace";

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-screen"><div className="spinner" aria-label="Loading" /></div>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const { user, loading } = useAuth();
  return (
    <>
      {!API_CONFIGURED && (
        <div className="config-banner" role="alert">
          VITE_API_URL is not set, so the app cannot reach the backend. Add it in Vercel project settings and redeploy.
        </div>
      )}
      <Routes>
        <Route path="/login" element={!loading && user ? <Navigate to="/app" replace /> : <AuthPage mode="login" />} />
        <Route path="/register" element={!loading && user ? <Navigate to="/app" replace /> : <AuthPage mode="register" />} />
        <Route path="/app" element={<Protected><Workspace /></Protected>} />
        <Route path="/app/:repoId" element={<Protected><Workspace /></Protected>} />
        <Route path="*" element={<Navigate to={user ? "/app" : "/login"} replace />} />
      </Routes>
    </>
  );
}
