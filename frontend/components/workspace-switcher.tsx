"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/components/workspace-context";

export function WorkspaceSwitcher({ variant = "block" }: { variant?: "block" | "menu" }) {
  const { me, users, asUserId, canViewOthers, setAsUserId, refreshUsers } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  if (!canViewOthers || !me || users.length < 2) return null;

  const current = users.find((row) => row.id === (asUserId ?? me.id)) ?? me;

  if (variant === "menu") {
    return (
      <div className="border-b border-line pb-1 mb-1">
        <p className="px-3 pb-1 text-[11px] text-muted">смотреть как</p>
        {users.map((row) => (
          <button
            key={row.id}
            type="button"
            onClick={() => setAsUserId(row.id === me.id ? null : row.id)}
            data-on={(asUserId ?? me.id) === row.id ? "true" : undefined}
            className="mega-item"
          >
            <span className="mega-k truncate">{row.email}</span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="relative mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full truncate text-left text-[13px] text-muted hover:text-ink"
      >
        {current.email}
      </button>
      {open && (
        <div className="absolute left-0 right-0 z-20 mt-2 max-h-64 space-y-1 overflow-y-auto rounded-xl border border-line bg-bg-soft p-2">
          {users.map((row) => (
            <div key={row.id} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setAsUserId(row.id === me.id ? null : row.id);
                  setOpen(false);
                }}
                className={`min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-left text-[13px] ${
                  (asUserId ?? me.id) === row.id ? "bg-fill-strong text-ink" : "text-muted hover:bg-fill hover:text-ink"
                }`}
              >
                {row.email}
              </button>
              {me.is_host && !row.is_host ? (
                <input
                  type="checkbox"
                  checked={Boolean(row.can_observe)}
                  disabled={busy === row.id}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => {
                    const next = e.target.checked;
                    setBusy(row.id);
                    void api
                      .patchUser(row.id, next)
                      .then(() => refreshUsers())
                      .finally(() => setBusy(null));
                  }}
                />
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
