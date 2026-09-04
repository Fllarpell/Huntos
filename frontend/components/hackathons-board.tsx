"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type {
  HackathonEventStatus,
  HackathonRegistrationStatus,
  HackathonRow,
  HackathonTrackStatus,
} from "@/lib/types";
import { GuideSpot } from "./guide";
import { RelativeTime } from "./relative-time";
import { SearchField } from "./search-field";

const REG_STATUS: Record<HackathonRegistrationStatus, { label: string; tone: string }> = {
  open: { label: "Регистрация открыта", tone: "bg-emerald-400/14 text-emerald-100" },
  closed: { label: "Регистрация закрыта", tone: "bg-white/8 text-muted" },
  unknown: { label: "Регистрация ?", tone: "bg-amber-400/14 text-amber-100" },
};

const EVENT_STATUS: Record<HackathonEventStatus, { label: string; tone: string }> = {
  upcoming: { label: "Скоро", tone: "bg-sky-400/14 text-sky-100" },
  active: { label: "Идёт", tone: "bg-accent/18 text-accent" },
  finished: { label: "Завершён", tone: "bg-white/8 text-muted" },
  unknown: { label: "Статус ?", tone: "bg-amber-400/14 text-amber-100" },
};

const TRACK_STATUS: { value: HackathonTrackStatus | ""; label: string }[] = [
  { value: "", label: "—" },
  { value: "watch", label: "Слежу" },
  { value: "applied", label: "Подался" },
  { value: "participating", label: "Участвую" },
  { value: "won", label: "Приз / оффер" },
  { value: "rejected", label: "Мимо" },
  { value: "skip", label: "Не интересно" },
];

type Filter = "all" | "open" | "new" | "mine";

function formatWhen(row: HackathonRow): string {
  const start = row.starts_at ? new Date(row.starts_at) : null;
  const end = row.ends_at ? new Date(row.ends_at) : null;
  const fmt = (d: Date) =>
    d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
  if (start && end && start.getTime() !== end.getTime()) return `${fmt(start)} — ${fmt(end)}`;
  if (start) return fmt(start);
  if (end) return fmt(end);
  return "даты уточняются";
}

function matchesQuery(row: HackathonRow, q: string): boolean {
  if (!q) return true;
  const hay = `${row.title} ${row.source_label} ${row.location || ""} ${row.tags || ""} ${row.description || ""} ${row.organizer || ""} ${row.prize_text || ""}`.toLowerCase();
  return hay.includes(q.toLowerCase());
}

function isCurrentHackathon(row: HackathonRow): boolean {
  if (row.event_status === "finished") return false;
  if (row.ends_at && Date.parse(row.ends_at) < Date.now()) return false;
  if (row.registration_status === "open") return true;
  if (row.event_status === "active") return true;
  if (row.starts_at && row.ends_at) {
    const now = Date.now();
    return Date.parse(row.starts_at) <= now && now <= Date.parse(row.ends_at);
  }
  return false;
}

export function HackathonsBoard() {
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<HackathonRow[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncNote, setSyncNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRows(await api.hackathons());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не загрузилось");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    return rows.filter((row) => {
      if (!matchesQuery(row, q.trim())) return false;
      if (filter === "open") return row.registration_status === "open" && row.event_status !== "finished";
      if (filter === "new") return isCurrentHackathon(row);
      if (filter === "mine") return Boolean(row.track.status);
      return true;
    });
  }, [rows, q, filter]);

  const stats = useMemo(() => {
    const open = rows.filter((row) => row.registration_status === "open" && row.event_status !== "finished").length;
    const fresh = rows.filter((row) => isCurrentHackathon(row)).length;
    const mine = rows.filter((row) => row.track.status).length;
    return { total: rows.length, open, fresh, mine };
  }, [rows]);

  async function syncNow() {
    setSyncing(true);
    setError(null);
    setSyncNote(null);
    try {
      const result = await api.syncHackathons();
      setSyncNote(`обновлено: +${result.created} новых, ${result.updated} обновлено`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Синк не удался");
    } finally {
      setSyncing(false);
    }
  }

  async function saveTrack(
    id: number,
    patch: { status?: HackathonTrackStatus | null; notes?: string | null },
  ) {
    setBusyId(id);
    setError(null);
    try {
      const saved = await api.saveHackathonTrack(id, patch);
      setRows((prev) => prev.map((row) => (row.id === id ? saved : row)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сохранилось");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      <GuideSpot id="hackathons.header">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[13px] tracking-[0.18em] text-muted uppercase">Карьера</p>
            <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Хакатоны</h1>
          </div>
          <div className="flex flex-col items-end gap-2">
            <button
              type="button"
              onClick={() => void syncNow()}
              disabled={syncing}
              className="inline-flex items-center gap-2 rounded-full bg-white/8 px-3 py-1.5 text-[13px] text-white hover:bg-white/12 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
              {syncing ? "Обновляю…" : "Обновить сейчас"}
            </button>
            <div className="flex flex-wrap justify-end gap-2 text-[12px] text-muted">
              <span className="rounded-full bg-white/6 px-3 py-1">всего {stats.total}</span>
              <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-emerald-100">открыто {stats.open}</span>
              <span className="rounded-full bg-sky-400/10 px-3 py-1 text-sky-100">новых {stats.fresh}</span>
              <span className="rounded-full bg-accent/10 px-3 py-1 text-accent">мои {stats.mine}</span>
            </div>
          </div>
        </div>
      </GuideSpot>

      <GuideSpot id="hackathons.filters" className="mt-6 flex flex-wrap items-center gap-3">
        <SearchField value={q} onChange={setQ} placeholder="Название, город, тег" className="w-full max-w-xs" />
        {(
          [
            ["all", "Все"],
            ["open", "Регистрация"],
            ["new", "Новые"],
            ["mine", "Мои"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-full px-3 py-1 text-[12px] ${
              filter === value ? "bg-white/10 text-white" : "text-muted hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </GuideSpot>

      {syncNote ? <p className="mt-4 text-[13px] text-muted">{syncNote}</p> : null}
      {error ? <p className="mt-4 rounded-xl bg-rose-400/10 px-4 py-3 text-sm text-rose-100">{error}</p> : null}

      <GuideSpot id="hackathons.list" className="mt-6 overflow-hidden rounded-2xl border border-line">
        <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,0.9fr)_minmax(0,0.8fr)_minmax(0,1fr)] gap-3 border-b border-line bg-white/3 px-4 py-3 text-[11px] tracking-[0.12em] text-muted uppercase">
          <span>Событие</span>
          <span>Статус</span>
          <span>Мой статус</span>
          <span>Заметки</span>
        </div>
        {visible.length === 0 ? (
          <p className="px-4 py-10 text-center text-[14px] text-muted">
            Пока пусто. Нажмите «Обновить сейчас» или подождите ночной синк.
          </p>
        ) : (
          visible.map((row) => {
            const reg = REG_STATUS[row.registration_status] || REG_STATUS.unknown;
            const ev = EVENT_STATUS[row.event_status] || EVENT_STATUS.unknown;
            const busy = busyId === row.id;
            return (
              <div
                key={row.id}
                className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,0.9fr)_minmax(0,0.8fr)_minmax(0,1fr)] gap-3 border-b border-line px-4 py-4 last:border-b-0"
              >
                <div className="flex min-w-0 gap-3">
                  {row.image_url ? (
                    <img
                      src={row.image_url}
                      alt=""
                      width={56}
                      height={56}
                      className="h-14 w-14 shrink-0 rounded-xl bg-white/8 object-cover"
                      referrerPolicy="no-referrer"
                    />
                  ) : null}
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex max-w-full items-center gap-1.5 truncate text-[15px] font-medium text-white hover:text-accent"
                      >
                        <span className="truncate">{row.title}</span>
                        <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-60" />
                      </a>
                      {isCurrentHackathon(row) ? (
                        <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[11px] text-sky-100">открыто</span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-[12px] text-muted">
                      {row.organizer ? <span className="text-white/80">{row.organizer}</span> : null}
                      {row.organizer ? " · " : ""}
                      {row.source_label}
                      {row.location ? ` · ${row.location}` : ""}
                      {row.format ? ` · ${row.format}` : ""}
                      {" · "}
                      {formatWhen(row)}
                    </p>
                    {row.prize_text ? (
                      <p className="mt-1 text-[13px] font-medium text-emerald-100/90">призовой фонд {row.prize_text}</p>
                    ) : null}
                    {row.description ? (
                      <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-muted">{row.description}</p>
                    ) : null}
                    {row.last_seen_at ? (
                      <p className="mt-1 text-[11px] text-muted">
                        проверено <RelativeTime iso={row.last_seen_at} />
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <span className={`w-fit rounded-full px-2.5 py-1 text-[12px] ${reg.tone}`}>{reg.label}</span>
                  <span className={`w-fit rounded-full px-2.5 py-1 text-[12px] ${ev.tone}`}>{ev.label}</span>
                </div>
                <div>
                  <select
                    disabled={busy}
                    value={row.track.status || ""}
                    onChange={(e) =>
                      void saveTrack(row.id, {
                        status: (e.target.value || null) as HackathonTrackStatus | null,
                        notes: row.track.notes,
                      })
                    }
                    className="w-full rounded-xl border border-line bg-black/20 px-2 py-1.5 text-[13px]"
                  >
                    {TRACK_STATUS.map((item) => (
                      <option key={item.value || "empty"} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <input
                    disabled={busy}
                    defaultValue={row.track.notes || ""}
                    key={`${row.id}-${row.track.updated_at || "x"}`}
                    placeholder="заметка"
                    onBlur={(e) => {
                      const next = e.target.value.trim() || null;
                      if (next === (row.track.notes || null)) return;
                      void saveTrack(row.id, { status: row.track.status, notes: next });
                    }}
                    className="w-full rounded-xl border border-line bg-black/20 px-3 py-1.5 text-[13px]"
                  />
                </div>
              </div>
            );
          })
        )}
      </GuideSpot>
    </div>
  );
}
