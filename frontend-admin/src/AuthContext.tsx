import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { verifyCredentials } from "./lib/api";

const STORAGE_KEY = "otc_admin_credentials";

interface AuthContextValue {
  credentials: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [credentials, setCredentials] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    verifyCredentials(stored).then((ok) => {
      if (ok) setCredentials(stored);
      else sessionStorage.removeItem(STORAGE_KEY);
      setLoading(false);
    });
  }, []);

  async function login(username: string, password: string): Promise<boolean> {
    const encoded = btoa(`${username}:${password}`);
    const ok = await verifyCredentials(encoded);
    if (ok) {
      sessionStorage.setItem(STORAGE_KEY, encoded);
      setCredentials(encoded);
    }
    return ok;
  }

  function logout() {
    sessionStorage.removeItem(STORAGE_KEY);
    setCredentials(null);
  }

  return <AuthContext.Provider value={{ credentials, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
