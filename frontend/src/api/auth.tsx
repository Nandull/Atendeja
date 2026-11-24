import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";

import { api, ApiError } from "./client";
import type { Role, Session } from "./types";

type AuthValue = {
  session: Session | null;
  loading: boolean;
  setSession: (s: Session) => void;
  logout: () => Promise<void>;
  can: (...roles: Role[]) => boolean;
};

const AuthContext = createContext<AuthValue | null>(null);

export const MANAGERS: Role[] = ["owner", "admin"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<Session>("/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 5 * 60_000,
  });

  const value: AuthValue = {
    session: data ?? null,
    loading: isLoading,
    setSession: (s) => {
      qc.setQueryData<Session | null>(["me"], s);
    },
    logout: async () => {
      await api("/auth/logout", { method: "POST" }).catch(() => undefined);
      // Recarrega a página: zera todo o cache em memória (dados do estabelecimento
      // anterior) sem corrida entre consultas que ainda estavam em andamento.
      window.location.assign("/entrar");
    },
    can: (...roles) => !!data && roles.includes(data.role),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
