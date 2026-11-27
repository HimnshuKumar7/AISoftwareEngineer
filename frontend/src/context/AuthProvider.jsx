import { useCallback, useEffect, useMemo, useState } from "react";
import { authApi } from "../api/auth";
import { setUnauthorizedHandler } from "../api/client";
import { tokenStore } from "../lib/tokenStore";
import { AuthContext } from "./AuthContext";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // Restore the session from a stored token.
  useEffect(() => {
    if (!tokenStore.get()) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(() => {
    const startSession = ({ access_token: token, user: signedIn }) => {
      tokenStore.set(token);
      setUser(signedIn);
    };
    return {
      user,
      loading,
      logout,
      login: async (email, password) => startSession(await authApi.login(email, password)),
      register: async (email, password, name) => startSession(await authApi.register(email, password, name)),
    };
  }, [user, loading, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
