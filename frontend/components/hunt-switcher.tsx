"use client";

import { useState } from "react";
import Link from "next/link";
import { useHunt } from "@/components/hunt-context";

export function HuntSwitcher({ variant = "block" }: { variant?: "block" | "bar" }) {
  const { hunts, activeHuntId, activeHunt, setActiveHuntId, createHunt } = useHunt();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const bar = variant === "bar";

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
    <div className={`relative ${bar ? "" : "mt-3"}`}>
      <button
        type="button"
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
        title="направление — какие вакансии в inbox"
        className={bar ? `top-link max-w-[160px] truncate${open ? " top-link-on" : ""}` : "w-full truncate text-left text-[13px] text-muted hover:text-ink"}
      >
        {label}
      </button>
      {open && (
        <div className={`absolute z-30 mt-1 space-y-1 rounded-xl border border-line bg-bg-soft p-2 ${bar ? "right-0 w-[240px]" : "left-0 right-0"}`}
        >
          <p className="px-2 pt-0.5 pb-1 text-[11px] leading-4 text-muted">направление — какие вакансии в inbox</p>
          <button
            type="button"
            onClick={() => void pick(null)}
            className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[13px] ${
              activeHuntId == null ? "bg-fill-strong text-ink" : "text-muted hover:bg-fill hover:text-ink"
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
                hunt.id === activeHuntId ? "bg-fill-strong text-ink" : "text-muted hover:bg-fill hover:text-ink"
              }`}
            >
              {hunt.name}
              {hunt.inbox_count > 0 ? ` · ${hunt.inbox_count}` : ""}
            </button>
          ))}
          <div className="border-t border-line pt-1">
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
                  placeholder="имя направления"
                  className="w-full bg-transparent px-2 py-1.5 text-[13px] outline-none"
                />
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setCreating(true)}
                className="block w-full px-2 py-1.5 text-left text-[13px] text-accent"
              >
                новое направление
              </button>
            )}
            <Link
              href="/thesis"
              onClick={() => setOpen(false)}
              className="block w-full px-2 py-1.5 text-left text-[13px] text-muted hover:text-ink"
            >
              все направления
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
