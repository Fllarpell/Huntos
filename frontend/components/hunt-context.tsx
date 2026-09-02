"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Hunt } from "@/lib/types";

type HuntContextValue = {
  hunts: Hunt[];
  activeHuntId: number | null;
  activeHunt: Hunt | null;
  setActiveHuntId: (id: number | null) => Promise<void>;
  createHunt: (name: string) => Promise<Hunt>;
  refresh: () => Promise<void>;
};

const HuntContext = createContext<HuntContextValue | null>(null);

export function HuntProvider({ children }: { children: React.ReactNode }) {
  const [hunts, setHunts] = useState<Hunt[]>([]);
  const [activeHuntId, setActive] = useState<number | null>(null);

  const apply = useCallback((items: Hunt[], active: number | null) => {
    setHunts(items);
    setActive(active);
  }, []);

  const refresh = useCallback(async () => {
    const data = await api.hunts();
    apply(data.items, data.active_hunt_id);
  }, [apply]);

  useEffect(() => {
    void refresh().catch(() => apply([], null));
  }, [refresh, apply]);

  const setActiveHuntId = useCallback(
    async (id: number | null) => {
      setActive(id);
      const data = await api.setActiveHunt(id);
      apply(data.items, data.active_hunt_id);
    },
    [apply],
  );

  const createHunt = useCallback(
    async (name: string) => {
      const saved = await api.saveThesis({ name: name.trim() || "Охота", enabled: true });
      await api.setActiveHunt(saved.id);
      await refresh();
      return {
        id: saved.id,
        name: saved.name,
        enabled: saved.enabled,
        inbox_count: 0,
        custom_fields: saved.custom_fields || [],
      };
    },
    [refresh],
  );

  const activeHunt = useMemo(
    () => hunts.find((item) => item.id === activeHuntId) ?? null,
    [hunts, activeHuntId],
  );

  const value = useMemo(
    () => ({ hunts, activeHuntId, activeHunt, setActiveHuntId, createHunt, refresh }),
    [hunts, activeHuntId, activeHunt, setActiveHuntId, createHunt, refresh],
  );

  return <HuntContext.Provider value={value}>{children}</HuntContext.Provider>;
}

export function useHunt() {
  const ctx = useContext(HuntContext);
  if (!ctx) {
    return {
      hunts: [] as Hunt[],
      activeHuntId: null as number | null,
      activeHunt: null,
      setActiveHuntId: async () => undefined,
      createHunt: async (name: string) => ({
        id: 0,
        name,
        enabled: true,
        inbox_count: 0,
        custom_fields: [],
      }),
      refresh: async () => undefined,
    };
  }
  return ctx;
}
