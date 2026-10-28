import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api, getToken, setToken } from "../api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: Record<string, unknown>) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>("/api/auth/me"));
    } catch (err) {
      // Only log out when the server explicitly rejects the token. Transient
      // network/server errors must never wipe a perfectly valid session token.
      if (err instanceof ApiError && err.status === 401) {
        setToken(null);
        setUser(null);
      }
    }
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email: string, password: string) => {
    const out = await api<{ token: string; user: User }>("/api/auth/login", {
      body: { email, password },
    });
    setToken(out.token);
    setUser(out.user);
    return out.user;
  };

  const register = async (payload: Record<string, unknown>) => {
    const out = await api<{ token: string; user: User }>("/api/auth/register", {
      body: payload,
    });
    setToken(out.token);
    setUser(out.user);
    return out.user;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
