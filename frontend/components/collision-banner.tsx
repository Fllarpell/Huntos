"use client";

import { useEffect, useMemo, useState } from "react";
import type { CollisionItem } from "@/lib/types";
import { NEXT_STEP_KINDS } from "@/lib/format";
import { defaultMinutes, hmRange } from "@/lib/schedule";

const BEFORE_MS = 3 * 60 * 60 * 1000;
const AFTER_MS = 30 * 60 * 1000;

function parseWhen(iso: string | null | undefined) {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

function endOf(item: CollisionItem, start: Date) {
  const explicit = parseWhen(item.ends_at);
  if (explicit) return explicit;
  return new Date(start.getTime() + defaultMinutes(item.next_step_kind) * 60 * 1000);
}

function inWindow(item: CollisionItem, now: Date) {
  const start = parseWhen(item.next_step_at);
  if (!start) return false;
  const end = endOf(item, start);
  return now.getTime() >= start.getTime() - BEFORE_MS && now.getTime() <= end.getTime() + AFTER_MS;
}

function kindLabel(kind: CollisionItem["next_step_kind"]) {
  return NEXT_STEP_KINDS.find((k) => k.value === kind)?.label ?? "собес";
}

function whenLabel(item: CollisionItem, now: Date) {
  const start = parseWhen(item.next_step_at);
  if (!start) return "";
  const end = endOf(item, start);
  if (now >= start && now <= end) return "идёт";
  if (now > end) return "только что";
  const min = Math.round((start.getTime() - now.getTime()) / 60000);
  if (min < 1) return "скоро";
  if (min < 60) return `через ${min} мин`;
  const hours = Math.round(min / 60);
  return `через ${hours} ч`;
}

export function CollisionBanner({
  items,
  onOpen,
}: {
  items: CollisionItem[];
  onOpen: (id: number) => void;
}) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const live = useMemo(
    () =>
      items
        .filter((item) => inWindow(item, now))
        .sort((a, b) => a.next_step_at.localeCompare(b.next_step_at)),
    [items, now],
  );

  if (!live.length) return null;
  const first = live[0];

  return (
    <button
      type="button"
      onClick={() => onOpen(first.id)}
      className="w-full border-b border-amber-400/20 bg-amber-400/[0.07] px-7 py-2.5 text-left"
    >
      <div className="space-y-0.5">
        {live.map((item) => (
          <p key={item.event_id ?? `${item.id}-${item.next_step_at}`} className="text-[13px] leading-5 text-amber-50">
            <span className="text-amber-200/80">Скоро · </span>
            {(item.company || "без компании").trim()} — {item.label || kindLabel(item.next_step_kind)}{" "}
            {hmRange(item.next_step_at, item.ends_at)} · {whenLabel(item, now)}
          </p>
        ))}
      </div>
    </button>
  );
}
