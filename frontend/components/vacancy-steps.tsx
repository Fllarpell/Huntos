"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { NEXT_STEP_KINDS, addMinutesLocal, minutesSpan, toDatetimeLocalValue, todayYmd } from "@/lib/format";
import { downloadVacancyIcs } from "@/lib/calendar";
import type { CollisionItem, Vacancy, VacancyEventItem } from "@/lib/types";
import { NextStepWhen } from "./next-step-when";
import { DURATIONS, defaultMinutes } from "@/lib/schedule";

function eventIcs(vacancy: Vacancy, event: VacancyEventItem) {
  return {
    id: event.id,
    title: vacancy.title,
    company: vacancy.company,
    notes: vacancy.notes,
    source_url: vacancy.source_url,
    telegram_alias: vacancy.telegram_alias,
    next_step_at: event.starts_at,
    next_step_kind: event.kind,
    label: event.display_label,
    ends_at: event.ends_at,
  };
}

function EventRow({
  vacancy,
  event,
  upcoming,
  onChanged,
  onError,
}: {
  vacancy: Vacancy;
  event: VacancyEventItem;
  upcoming: CollisionItem[];
  onChanged: (v: Vacancy) => void;
  onError: (message: string) => void;
}) {
  const [when, setWhen] = useState(toDatetimeLocalValue(event.starts_at));
  const [kind, setKind] = useState(event.kind);
  const [label, setLabel] = useState(event.label || "");
  const [minutes, setMinutes] = useState(minutesSpan(event.starts_at, event.ends_at) || defaultMinutes(event.kind));
  const [busy, setBusy] = useState(false);
  const onChangedRef = useRef(onChanged);
  const onErrorRef = useRef(onError);
  onChangedRef.current = onChanged;
  onErrorRef.current = onError;

  useEffect(() => {
    setWhen(toDatetimeLocalValue(event.starts_at));
    setKind(event.kind);
    setLabel(event.label || "");
    setMinutes(minutesSpan(event.starts_at, event.ends_at) || defaultMinutes(event.kind));
  }, [event.id, event.starts_at, event.ends_at, event.kind, event.label]);

  useEffect(() => {
    const starts = when ? `${when}:00` : "";
    const ends = when ? `${addMinutesLocal(when, minutes)}:00` : "";
    const savedWhen = toDatetimeLocalValue(event.starts_at);
    const savedLabel = event.label || "";
    const savedMinutes = minutesSpan(event.starts_at, event.ends_at) || defaultMinutes(event.kind);
    if (when === savedWhen && kind === event.kind && label === savedLabel && minutes === savedMinutes) return;
    if (!when) return;
    const t = setTimeout(() => {
      setBusy(true);
      void api
        .patchEvent(event.id, {
          kind,
          starts_at: starts,
          ends_at: ends,
          label: label.trim() || null,
        })
        .then((saved) => onChangedRef.current(saved))
        .catch((e) => onErrorRef.current(e instanceof Error ? e.message : "Не сохранилось"))
        .finally(() => setBusy(false));
    }, 500);
    return () => clearTimeout(t);
  }, [when, kind, label, minutes, event.id, event.starts_at, event.ends_at, event.kind, event.label]);

  const day = when.slice(0, 10);
  const peers = day
    ? upcoming.filter((item) => item.event_id !== event.id && item.next_step_at.slice(0, 10) === day)
    : [];

  return (
    <div className="rounded-2xl border border-line bg-white/4 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="text-[14px] font-medium">{event.display_label}</p>
        {busy && <p className="text-[12px] text-muted">сохраняю…</p>}
      </div>
      <NextStepWhen
        value={when}
        kind={kind}
        onChange={(next) => {
          if (!next.next_step_at) {
            setBusy(true);
            void api
              .deleteEvent(event.id)
              .then(onChanged)
              .catch((e) => onError(e instanceof Error ? e.message : "Не удалилось"))
              .finally(() => setBusy(false));
            return;
          }
          setWhen(next.next_step_at);
          const nextKind = (next.next_step_kind || "interview") as VacancyEventItem["kind"];
          if (nextKind !== kind && minutes === defaultMinutes(kind)) setMinutes(defaultMinutes(nextKind));
          setKind(nextKind);
        }}
      />
      <div className="mt-3">
        <p className="mb-1.5 text-[12px] text-muted">Длительность</p>
        <div className="flex flex-wrap gap-1.5">
          {DURATIONS.map((item) => (
            <button
              key={item}
              type="button"
              className={`rounded-full px-2.5 py-1 text-[12px] ${
                minutes === item ? "bg-accent/18 text-accent ring-1 ring-accent/35" : "bg-white/5 text-muted hover:text-white"
              }`}
              onClick={() => setMinutes(item)}
            >
              {item} мин
            </button>
          ))}
        </div>
        <p className="mt-2 text-[12px] tabular-nums text-muted">
          {when ? `${when.slice(11, 16)}–${addMinutesLocal(when, minutes).slice(11, 16)}` : ""}
        </p>
      </div>
      <input
        className="mt-3"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="например: скрин, собес 1"
      />
      {peers.length > 0 && (
        <p className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/8 px-3 py-2 text-[13px] leading-5 text-amber-100">
          В этот день ещё{" "}
          {peers
            .map((item) => {
              const step =
                item.label || NEXT_STEP_KINDS.find((k) => k.value === item.next_step_kind)?.label || "собес";
              const time = item.next_step_at.slice(11, 16);
              const company = (item.company || "").trim() || "без компании";
              return `${company} — ${step} ${time}`;
            })
            .join(", ")}
          .
        </p>
      )}
      {event.google_sync_error && (
        <p className="mt-3 rounded-xl bg-rose-400/10 px-3 py-2 text-[13px] text-rose-200">
          Google: {event.google_sync_error}
        </p>
      )}
      {vacancy.calendar_connected && event.google_event_id && !event.google_sync_error && (
        <p className="mt-3 text-[13px] text-accent">создано в календаре Hunt</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-xl bg-white/8 px-3 py-1.5 text-sm"
          onClick={() => downloadVacancyIcs(eventIcs(vacancy, event))}
        >
          Скачать .ics
        </button>
        <button
          type="button"
          className="text-[13px] text-rose-200/80 hover:text-rose-100"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .deleteEvent(event.id)
              .then(onChanged)
              .catch((e) => onError(e instanceof Error ? e.message : "Не удалилось"))
              .finally(() => setBusy(false));
          }}
        >
          Удалить шаг
        </button>
      </div>
    </div>
  );
}

export function VacancySteps({
  vacancy,
  upcoming,
  onChanged,
  onError,
}: {
  vacancy: Vacancy;
  upcoming: CollisionItem[];
  onChanged: (v: Vacancy) => void;
  onError: (message: string) => void;
}) {
  const events = vacancy.events || [];
  const [busy, setBusy] = useState(false);

  return (
    <section>
      <h3 className="mb-3 text-[12px] tracking-[0.14em] text-muted uppercase">Шаги</h3>
      <div className="space-y-3">
        {events.map((event) => (
          <EventRow
            key={event.id}
            vacancy={vacancy}
            event={event}
            upcoming={upcoming}
            onChanged={onChanged}
            onError={onError}
          />
        ))}
      </div>
      {!events.length && <p className="text-[13px] text-muted">Нет скрина или собеса. Добавь шаг — появится во «Времени».</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          className="rounded-xl bg-white/8 px-3 py-1.5 text-sm disabled:opacity-40"
          onClick={() => {
            setBusy(true);
            void api
              .addEvent(vacancy.id, {
                kind: "interview",
                starts_at: `${todayYmd()}T15:00:00`,
                ends_at: `${todayYmd()}T16:00:00`,
              })
              .then(onChanged)
              .catch((e) => onError(e instanceof Error ? e.message : "Не добавилось"))
              .finally(() => setBusy(false));
          }}
        >
          {busy ? "Добавляю…" : "Добавить шаг"}
        </button>
        {!vacancy.calendar_connected && (
          <Link href="/settings" className="text-[13px] text-accent hover:underline">
            Подключить Google Calendar
          </Link>
        )}
      </div>
    </section>
  );
}
