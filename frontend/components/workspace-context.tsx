"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setAsUser, type AuthUser } from "@/lib/api";
import { setPendingFirstTour } from "@/lib/guide";

const STORAGE = "hunt-as-user";

type WorkspaceValue = {
  me: AuthUser | null;
  users: AuthUser[];
  asUserId: number | null;
  viewed: AuthUser | null;
  canViewOthers: boolean;
  setAsUserId: (id: number | null) => void;
  refreshUsers: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<AuthUser | null>(null);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [asUserId, setAs] = useState<number | null>(null);

  const refreshUsers = useCallback(async () => {
    const user = await api.me();
    setMe(user);
    if (new URLSearchParams(window.location.search).get("new") === "1") {
      setPendingFirstTour(user.id);
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (!user.is_host && !user.can_observe) {
      setUsers([]);
      setAsUser(null);
      setAs(null);
      return;
    }
    const list = await api.users();
    setUsers(list);
    const stored = Number(window.localStorage.getItem(STORAGE) || 0) || null;
    const next = stored && list.some((row) => row.id === stored) && stored !== user.id ? stored : null;
    setAsUser(next);
    setAs(next);
  }, []);

  useEffect(() => {
    void refreshUsers().catch(() => {
      if (window.location.pathname !== "/login") window.location.href = "/login";
    });
  }, [refreshUsers]);

  const setAsUserId = useCallback(
    (id: number | null) => {
      const next = id && me && id !== me.id ? id : null;
      setAsUser(next);
      setAs(next);
      if (next) window.localStorage.setItem(STORAGE, String(next));
      else window.localStorage.removeItem(STORAGE);
    },
    [me],
  );

  const viewed = useMemo(
    () => (asUserId != null ? users.find((row) => row.id === asUserId) ?? null : me),
    [asUserId, users, me],
  );

  const value = useMemo(
    () => ({
      me,
      users,
      asUserId,
      viewed,
      canViewOthers: Boolean(me?.is_host || me?.can_observe),
      setAsUserId,
      refreshUsers,
    }),
    [me, users, asUserId, viewed, setAsUserId, refreshUsers],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    return {
      me: null,
      users: [] as AuthUser[],
      asUserId: null as number | null,
      viewed: null as AuthUser | null,
      canViewOthers: false,
      setAsUserId: (_id: number | null) => undefined,
      refreshUsers: async () => undefined,
    };
  }
  return ctx;
}
