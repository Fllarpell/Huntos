"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { downloadPingIcs, pingEventTitle } from "@/lib/calendar";
import { formatNextStepBadge, toDatetimeLocalValue, vacancyTelegramUrl } from "@/lib/format";
import type { NudgeGroup, PingSlot, Vacancy } from "@/lib/types";
import { CompanyMark } from "./company-mark";
import { NextStepWhen } from "./next-step-when";
import { TelegramChatLink } from "./telegram-chat-link";

function silenceLabel(days: number | null | undefined) {
  if (days == null) return "тишина";
  if (days === 1) return "1 день";
  if (days >= 2 && days <= 4) return `${days} дня`;
  return `${days} дней`;
}

function withSeconds(value: string) {
  return value.length === 16 ? `${value}:00` : value;
}

export function NudgeQueue({
  afterDays,
  groups,
  calendarConnected,
  onOpen,
  onChanged,
}: {
  afterDays: number;
  groups: NudgeGroup[];
  calendarConnected?: boolean;
  onOpen: (id: number) => void;
  onChanged: () => void;
}) {
  const items = useMemo(() => groups.flatMap((g) => g.items), [groups]);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const connected = calendarConnected ?? groups.some((g) => g.slot?.calendar_connected);

  useEffect(() => {
    setChecked(new Set(items.map((v) => v.id)));
  }, [items]);

  if (!groups.length) return null;
  const selected = items.filter((v) => checked.has(v.id));

  function toggle(id: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function ping(ids: number[]) {
    if (!ids.length) return;
    setBusy(true);
    setError(null);
    try {
      await api.nudgePinged(ids);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не отметилось");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="border-b border-amber-400/20 bg-amber-400/[0.07] px-7 py-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] tracking-[0.12em] text-amber-200/80 uppercase">Пингануть</p>
          <p className="mt-1 text-[14px] leading-5 text-amber-50">
            {items.length} молчат от {afterDays} дней. Это напоминание написать ещё раз — карточки остаются в «жду ответа». В календарь ставится один слот на всю пачку, не встреча на каждую.
          </p>
        </div>
        <button
          type="button"
          disabled={busy || !selected.length}
          className="rounded-xl bg-amber-400/20 px-3 py-1.5 text-sm text-amber-100 disabled:opacity-40"
          onClick={() => void ping(selected.map((v) => v.id))}
        >
          {busy ? "Отмечаю…" : `Пинганул выбранные · ${selected.length}`}
        </button>
      </div>
      {error && <p className="text-sm text-rose-200">{error}</p>}
      {groups.map((group) => (
        <div key={group.thesis_id ?? "none"} className="space-y-1">
          <p className="text-[12px] text-amber-200/70">
            {group.thesis_name || "без тезиса"} · {group.items.length}
          </p>
          {group.slot && (
            <PingSlotCard
              group={group}
              slot={group.slot}
              connected={Boolean(connected || group.slot.calendar_connected)}
            />
          )}
          {group.items.map((v: Vacancy) => {
            const chat = vacancyTelegramUrl(v);
            return (
              <div key={v.id} className="flex items-center gap-3 rounded-xl bg-black/15 px-3 py-2">
                <input
                  type="checkbox"
                  checked={checked.has(v.id)}
                  onChange={() => toggle(v.id)}
                  className="h-4 w-4 accent-amber-300"
                />
                <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => onOpen(v.id)}>
                  <CompanyMark vacancy={v} size={24} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium">{v.company || "без компании"}</span>
                    <span className="block truncate text-[12px] text-amber-100/60">{v.title}</span>
                  </span>
                  <span className="shrink-0 text-[12px] tabular-nums text-amber-100">
                    {silenceLabel(v.silence_days)}
                  </span>
                </button>
                {chat && <TelegramChatLink href={chat} className="hidden shrink-0 text-[12px] sm:block" />}
                {v.telegram_message && (
                  <button
                    type="button"
                    className="shrink-0 rounded-lg bg-white/8 px-2 py-1 text-[11px]"
                    onClick={() => void navigator.clipboard.writeText(v.telegram_message || "")}
                  >
                    Копировать
                  </button>
                )}
                <button
                  type="button"
                  disabled={busy}
                  className="shrink-0 rounded-lg bg-amber-400/20 px-2 py-1 text-[11px] text-amber-100"
                  onClick={() => void ping([v.id])}
                >
                  Пинганул
                </button>
              </div>
            );
          })}
        </div>
      ))}
    </section>
  );
}

function PingSlotCard({
  group,
  slot: initial,
  connected,
}: {
  group: NudgeGroup;
  slot: PingSlot;
  connected: boolean;
}) {
  const [slot, setSlot] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSlot(initial);
  }, [initial]);

  const when = toDatetimeLocalValue(slot.ping_at);
  const title = pingEventTitle(slot.label || group.thesis_name || "без тезиса", slot.card_count);
  const badge = formatNextStepBadge(slot.ping_at);

  async function save(pingAt: string) {
    if (!pingAt) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.nudgeSlot({
        thesis_id: group.thesis_id,
        ping_at: withSeconds(pingAt),
      });
      setSlot(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Слот не сохранился");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mb-2 rounded-xl border border-amber-400/15 bg-black/20 px-3 py-3 space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[13px] text-amber-50">
          Слот пинга{badge ? ` · ${badge}` : ""}. Когда написать ещё раз — один слот на пачку, не {slot.card_count} встреч.
        </p>
        {saving && <p className="text-[12px] text-amber-200/70">Сохраняю…</p>}
      </div>
      <NextStepWhen
        value={when}
        kind=""
        showKind={false}
        onChange={(next) => {
          if (next.next_step_at) void save(next.next_step_at);
        }}
      />
      {error && <p className="text-[13px] text-rose-200">{error}</p>}
      {slot.google_sync_error && (
        <p className="rounded-xl bg-rose-400/10 px-3 py-2 text-[13px] text-rose-200">Google: {slot.google_sync_error}</p>
      )}
      {slot.ping_at && connected && slot.google_event_id && !slot.google_sync_error && (
        <p className="text-[13px] text-amber-100">создано в календаре HuntOS</p>
      )}
      {slot.ping_at && (
        <button
          type="button"
          className="rounded-xl bg-white/8 px-3 py-1.5 text-sm"
          onClick={() =>
            downloadPingIcs({
              id: slot.id,
              title,
              ping_at: slot.ping_at || "",
              details: "HuntOS — один слот пинга на пачку, не встреча на каждую карточку.",
            })
          }
        >
          Скачать .ics
        </button>
      )}
    </div>
  );
}
