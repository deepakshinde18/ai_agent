import { useCallback, useMemo, useState, type ReactNode } from "react";

import { loginUser, registerUser } from "../api/client";
import { AuthContext } from "./context";
import { decodeJwt, isTokenExpired } from "./jwt";

const STORAGE_KEY = "insight_agent_token";

function readStoredToken(): string | null {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored || isTokenExpired(stored)) {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
  return stored;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStoredToken());

  const setSession = useCallback((newToken: string) => {
    localStorage.setItem(STORAGE_KEY, newToken);
    setToken(newToken);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await loginUser(email, password);
      setSession(access_token);
    },
    [setSession],
  );

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const { access_token } = await registerUser(email, password, fullName);
      setSession(access_token);
    },
    [setSession],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
  }, []);

  const email = useMemo(() => (token ? decodeJwt(token)?.email ?? null : null), [token]);

  const value = useMemo(
    () => ({ token, email, isAuthenticated: Boolean(token), login, register, logout }),
    [token, email, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
