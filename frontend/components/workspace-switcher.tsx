"use client";

import { useState } from "react";
import { useWorkspace } from "@/components/workspace-context";

export function WorkspaceSwitcher() {
  const { me, users, asUserId, canViewOthers, setAsUserId } = useWorkspace();
  const [open, setOpen] = useState(false);

  if (!canViewOthers || !me || users.length < 2) return null;

  const current = users.find((row) => row.id === (asUserId ?? me.id)) ?? me;
  const watching = asUserId != null && asUserId !== me.id;

  return (
    <div className="relative mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full truncate text-left text-[13px]"
      >
        <span className={watching ? "text-amber-100" : "text-muted hover:text-white"}>
          {watching ? `смотришь ${current.email}` : "свой аккаунт"}
        </span>
      </button>
      {open && (
        <div className="absolute left-0 right-0 z-20 mt-2 max-h-64 space-y-1 overflow-y-auto rounded-xl border border-line bg-bg-soft p-2">
          <button
            type="button"
            onClick={() => {
              setAsUserId(null);
              setOpen(false);
            }}
            className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[13px] ${
              asUserId == null ? "text-white" : "text-muted hover:text-white"
            }`}
          >
            я · {me.email}
          </button>
          {users
            .filter((row) => row.id !== me.id)
            .map((row) => (
              <button
                key={row.id}
                type="button"
                onClick={() => {
                  setAsUserId(row.id);
                  setOpen(false);
                }}
                className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[13px] ${
                  asUserId === row.id ? "text-white" : "text-muted hover:text-white"
                }`}
              >
                {row.email}
                {row.is_host ? " · хост" : row.can_observe ? " · смотрит всех" : ""}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
