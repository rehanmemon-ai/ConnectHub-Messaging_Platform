/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import type { OwnUser } from "../types/api";

interface AuthValue {
  user: OwnUser | null;
  status: "loading" | "authenticated" | "anonymous";
  login: (identifier: string, password: string) => Promise<void>;
  register: (input: {
    username: string;
    email: string;
    display_name: string;
    password: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (input: { username?: string; display_name?: string }) => Promise<void>;
  invalidate: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<OwnUser | null>(null);
  const [status, setStatus] = useState<AuthValue["status"]>("loading");

  useEffect(() => {
    const controller = new AbortController();
    api<{ user: OwnUser }>("/api/v1/users/me", { signal: controller.signal })
      .then((result) => {
        setUser(result.user);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setUser(null);
        setStatus("anonymous");
      });
    return () => controller.abort();
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      status,
      async login(identifier, password) {
        const result = await api<{ user: OwnUser }>("/api/v1/auth/login", {
          method: "POST",
          csrf: false,
          body: { identifier, password },
        });
        setUser(result.user);
        setStatus("authenticated");
      },
      async register(input) {
        await api("/api/v1/auth/register", { method: "POST", csrf: false, body: input });
      },
      async logout() {
        await api("/api/v1/auth/logout", { method: "POST" });
        setUser(null);
        setStatus("anonymous");
        window.dispatchEvent(new CustomEvent("connecthub:logout"));
      },
      async updateProfile(input) {
        const result = await api<{ user: OwnUser }>("/api/v1/users/me", {
          method: "PATCH",
          body: input,
        });
        setUser(result.user);
      },
      invalidate() {
        setUser(null);
        setStatus("anonymous");
        window.dispatchEvent(new CustomEvent("connecthub:logout"));
      },
    }),
    [status, user],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
