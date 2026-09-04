"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import type { InternshipCatalogStatus, InternshipKind, InternshipRow, InternshipTrackStatus } from "@/lib/types";
import { CompanyMark } from "./company-mark";
import { GuideSpot } from "./guide";
import { RelativeTime } from "./relative-time";
import { SearchField } from "./search-field";

const CATALOG_STATUS: Record<InternshipCatalogStatus, { label: string; tone: string }> = {
  open: { label: "Открыта", tone: "bg-emerald-400/14 text-emerald-100" },
  waiting: { label: "Ждём набор", tone: "bg-sky-400/14 text-sky-100" },
  closed: { label: "Закрыта", tone: "bg-white/8 text-muted" },
  monitor: { label: "Мониторим", tone: "bg-amber-400/14 text-amber-100" },
};

const TRACK_STATUS: { value: InternshipTrackStatus | ""; label: string }[] = [
  { value: "", label: "—" },
  { value: "watch", label: "Слежу" },
  { value: "applied", label: "Подался" },
  { value: "screening", label: "Отбор" },
  { value: "offer", label: "Оффер" },
  { value: "rejected", label: "Отказ" },
  { value: "skip", label: "Не интересно" },
];

const TRACK_TONE: Record<InternshipTrackStatus, string> = {
  watch: "text-sky-100",
  applied: "text-accent",
  screening: "text-amber-100",
  offer: "text-emerald-100",
  rejected: "text-rose-100",
  skip: "text-muted",
};

type Filter = "all" | "open" | "mine";

function matchesQuery(row: InternshipRow, q: string): boolean {
  if (!q) return true;
  const hay = `${row.name} ${row.company} ${row.hint}`.toLowerCase();
  return hay.includes(q.toLowerCase());
}

function rowStatus(row: InternshipRow): InternshipCatalogStatus {
  return row.live_status ?? row.catalog_status;
}

export function InternshipsBoard() {
  const [kind, setKind] = useState<InternshipKind>("internship");
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<InternshipRow[]>([]);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.internships(kind);
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не загрузилось");
    }
  }, [kind]);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    return rows.filter((row) => {
      if (!matchesQuery(row, q.trim())) return false;
      if (filter === "open") return rowStatus(row) === "open";
      if (filter === "mine") return Boolean(row.track.status);
      return true;
    });
  }, [rows, q, filter]);

  const stats = useMemo(() => {
    const open = rows.filter((row) => rowStatus(row) === "open").length;
    const mine = rows.filter((row) => row.track.status).length;
    return { total: rows.length, open, mine };
  }, [rows]);

  async function saveTrack(
    slug: string,
    patch: { status?: InternshipTrackStatus | null; notes?: string | null; applied_at?: string | null },
  ) {
    setBusySlug(slug);
    setError(null);
    try {
      const saved = await api.saveInternshipTrack(slug, patch);
      setRows((prev) => prev.map((row) => (row.slug === slug ? saved : row)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сохранилось");
    } finally {
      setBusySlug(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      <GuideSpot id="internships.header">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[13px] tracking-[0.18em] text-muted uppercase">Карьера</p>
            <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Стажировки</h1>
          </div>
          <div className="flex flex-wrap gap-2 text-[12px] text-muted">
            <span className="rounded-full bg-white/6 px-3 py-1">всего {stats.total}</span>
            <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-emerald-100">открыто {stats.open}</span>
            <span className="rounded-full bg-accent/10 px-3 py-1 text-accent">мои {stats.mine}</span>
          </div>
        </div>
      </GuideSpot>

      <GuideSpot id="internships.tabs" className="mt-6 flex flex-wrap gap-2">
        {(
          [
            ["internship", "Стажировки"],
            ["school", "Школы"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setKind(value)}
            className={`rounded-full px-3 py-1.5 text-[13px] ${
              kind === value ? "bg-accent/18 text-accent" : "bg-white/5 text-muted hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </GuideSpot>

      <GuideSpot id="internships.filters" className="mt-4 flex flex-wrap items-center gap-3">
        <SearchField value={q} onChange={setQ} placeholder="Компания или программа" className="w-full max-w-xs" />
        {(
          [
            ["all", "Все"],
            ["open", "Открытые"],
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

      {error ? <p className="mt-4 rounded-xl bg-rose-400/10 px-4 py-3 text-sm text-rose-100">{error}</p> : null}

      <GuideSpot id="internships.list" className="mt-6 overflow-hidden rounded-2xl border border-line">
        <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,0.8fr)_minmax(0,0.9fr)_minmax(0,1.2fr)] gap-3 border-b border-line bg-white/3 px-4 py-3 text-[11px] tracking-[0.12em] text-muted uppercase">
          <span>Программа</span>
          <span>Набор</span>
          <span>Мой статус</span>
          <span>Заметки</span>
        </div>
        <div className="divide-y divide-line">
          {visible.map((row) => {
            const status = rowStatus(row);
            const catalog = CATALOG_STATUS[status];
            const trackStatus = row.track.status;
            return (
              <div
                key={row.slug}
                className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,0.8fr)_minmax(0,0.9fr)_minmax(0,1.2fr)] gap-3 px-4 py-3 text-[14px] hover:bg-white/2"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <CompanyMark company={row.company} icon={row.logo_url} size={32} />
                  <div className="min-w-0">
                    <div className="flex items-start gap-2">
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noreferrer"
                        className="group inline-flex min-w-0 items-center gap-1.5 font-medium text-white hover:text-accent"
                      >
                        <span className="truncate">{row.name}</span>
                        <ExternalLink size={13} className="shrink-0 opacity-50 group-hover:opacity-100" />
                      </a>
                    </div>
                    <p className="mt-0.5 truncate text-[12px] text-muted">{row.company}</p>
                    {row.hint ? <p className="mt-1 text-[12px] leading-5 text-muted/80">{row.hint}</p> : null}
                  </div>
                </div>
                <div className="flex flex-col items-start gap-1 pt-0.5">
                  <span className={`rounded-full px-2.5 py-1 text-[12px] ${catalog.tone}`}>{catalog.label}</span>
                  {row.checked_at ? (
                    <span className="text-[11px] text-muted/70">
                      проверено <RelativeTime iso={row.checked_at} />
                    </span>
                  ) : null}
                  {row.check_error ? (
                    <span className="text-[11px] text-amber-100/80">не удалось проверить</span>
                  ) : null}
                </div>
                <div className="min-w-0">
                  <select
                    value={trackStatus || ""}
                    disabled={busySlug === row.slug}
                    onChange={(e) => {
                      const next = (e.target.value || null) as InternshipTrackStatus | null;
                      void saveTrack(row.slug, {
                        status: next,
                        notes: row.track.notes,
                        applied_at: row.track.applied_at,
                      });
                    }}
                    className={`w-full rounded-lg border border-line bg-bg-soft px-2 py-1.5 text-[13px] outline-none ${
                      trackStatus ? TRACK_TONE[trackStatus] : "text-muted"
                    }`}
                  >
                    {TRACK_STATUS.map((opt) => (
                      <option key={opt.value || "none"} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="min-w-0">
                  <input
                    type="text"
                    defaultValue={row.track.notes || ""}
                    key={`${row.slug}:${row.track.updated_at || "new"}`}
                    disabled={busySlug === row.slug}
                    placeholder="дедлайн, этап, контакт…"
                    onBlur={(e) => {
                      const next = e.target.value.trim() || null;
                      if (next === (row.track.notes || null)) return;
                      void saveTrack(row.slug, {
                        status: row.track.status,
                        notes: next,
                        applied_at: row.track.applied_at,
                      });
                    }}
                    className="w-full rounded-lg border border-line bg-bg-soft px-2 py-1.5 text-[13px] outline-none placeholder:text-muted/60"
                  />
                </div>
              </div>
            );
          })}
          {!visible.length ? (
            <p className="px-4 py-8 text-center text-[13px] text-muted">Ничего не нашлось — смените фильтр или запрос.</p>
          ) : null}
        </div>
      </GuideSpot>

      <p className="mt-6 text-[12px] leading-5 text-muted/80">
        Статусы набора («Открыта», «Ждём», «Закрыта») обновляются автоматически раз в сутки по публичным
        страницам программ. Перед подачей всё равно проверяйте сайт компании. Новую программу — напишите, добавим.
      </p>
    </div>
  );
}
