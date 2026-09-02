"use client";

import { useState } from "react";
import { useHunt } from "@/components/hunt-context";

export function HuntSwitcher() {
  const { hunts, activeHuntId, activeHunt, setActiveHuntId, createHunt } = useHunt();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const label = activeHunt?.name || "все карточки";

  async function pick(id: number | null) {
    setOpen(false);
    setCreating(false);
    if (id === activeHuntId) return;
    setBusy(true);
    try {
      await setActiveHuntId(id);
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    const label = name.trim();
    if (!label) return;
    setBusy(true);
    try {
      await createHunt(label);
      setName("");
      setCreating(false);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative mt-3">
      <button
        type="button"
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
        className="w-full truncate text-left text-[13px] text-muted hover:text-white"
      >
        {label}
      </button>
      {open && (
        <div className="absolute left-0 right-0 z-20 mt-2 space-y-1 rounded-xl border border-line bg-bg-soft p-2">
          <button
            type="button"
            onClick={() => void pick(null)}
            className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[13px] ${
              activeHuntId == null ? "text-white" : "text-muted hover:text-white"
            }`}
          >
            все карточки
          </button>
          {hunts.map((hunt) => (
            <button
              key={hunt.id}
              type="button"
              onClick={() => void pick(hunt.id)}
              className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[13px] ${
                hunt.id === activeHuntId ? "text-white" : "text-muted hover:text-white"
              }`}
            >
              {hunt.name}
              {hunt.inbox_count > 0 ? ` · ${hunt.inbox_count}` : ""}
            </button>
          ))}
          <div className="border-t border-white/[0.06] pt-1">
            {creating ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void submit();
                }}
              >
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="имя охоты"
                  className="w-full bg-transparent px-2 py-1.5 text-[13px] outline-none"
                />
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setCreating(true)}
                className="block w-full px-2 py-1.5 text-left text-[13px] text-accent"
              >
                новая охота
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
