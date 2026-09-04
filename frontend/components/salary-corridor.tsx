"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import {
  GETMATCH_SALARIES_URL,
  HABR_SALARIES_URL,
  LEVELS_FYI_URL,
  corridorLabel,
  formatCorridorK,
  type SalaryCorridor,
} from "@/lib/salary-corridor";
import type { DonorSalaryRow, SalaryMarket } from "@/lib/types";

function hoverPay(n: number): number {
  return Math.round(n / 1000) * 1000;
}

function CorridorStrip({
  corridor,
  threshold,
  compact,
  busy,
}: {
  corridor: SalaryCorridor;
  threshold?: number | null;
  compact?: boolean;
  busy?: boolean;
}) {
  const p25 = corridor.p25 as number;
  const median = corridor.median as number;
  const p75 = corridor.p75 as number;
  const span = Math.max(1, p75 - p25);
  const pad = span * 0.15;
  const lo = Math.min(p25, threshold ?? p25) - pad;
  const hi = Math.max(p75, threshold ?? p75) + pad;
  const width = Math.max(1, hi - lo);
  const bandLeft = ((p25 - lo) / width) * 100;
  const bandWidth = ((p75 - p25) / width) * 100;
  const medianLeft = ((median - lo) / width) * 100;
  const thresholdLeft =
    threshold != null && threshold > 0 ? ((threshold - lo) / width) * 100 : null;
  const track = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<{ x: number; pay: number; label: string } | null>(null);

  function read(clientX: number) {
    const el = track.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    if (box.width <= 0) return;
    const t = Math.min(1, Math.max(0, (clientX - box.left) / box.width));
    let pay = lo + t * width;
    const px = t * box.width;
    const marks: { v: number; label: string }[] = [
      { v: p25, label: "низ типичного" },
      { v: median, label: "медиана" },
      { v: p75, label: "верх типичного" },
    ];
    if (threshold != null && threshold > 0) marks.push({ v: threshold, label: "твой порог" });
    const near = marks.find((mark) => Math.abs(((mark.v - lo) / width) * box.width - px) <= 10);
    let label = "типичный диапазон";
    if (near) {
      pay = near.v;
      label = near.label;
    } else {
      if (pay < p25) label = "ниже типичного";
      else if (pay > p75) label = "выше типичного";
      pay = hoverPay(pay);
    }
    setTip({ x: t * 100, pay, label });
  }

  return (
    <div>
      <p className={compact ? "text-[12px]" : "text-[13px]"}>
        {tip ? (
          <>
            <span className="tabular-nums text-white">{formatCorridorK(tip.pay)}</span>
            <span className="text-muted"> · {tip.label}</span>
          </>
        ) : (
          <>
            <span className="text-muted">рынок </span>
            <span className="tabular-nums text-white">{corridorLabel(corridor)}</span>
            {busy ? <span className="text-muted"> · …</span> : null}
          </>
        )}
      </p>
      <div
        className={`relative cursor-crosshair ${compact ? "py-1" : "py-2"}`}
        onPointerMove={(e) => read(e.clientX)}
        onPointerLeave={() => setTip(null)}
      >
        <div ref={track} className={`relative rounded-full bg-white/8 ${compact ? "h-1.5" : "h-2"}`}>
          <div
            className={`absolute top-0 rounded-full bg-emerald-400/40 ${compact ? "h-1.5" : "h-2"}`}
            style={{ left: `${bandLeft}%`, width: `${bandWidth}%` }}
          />
          <div
            className="absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-100"
            style={{ left: `${medianLeft}%` }}
          />
          {thresholdLeft != null ? (
            <div
              className="absolute top-1/2 h-3.5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent"
              style={{ left: `${Math.min(100, Math.max(0, thresholdLeft))}%` }}
            />
          ) : null}
          {tip ? (
            <div
              className="pointer-events-none absolute top-1/2 h-3.5 w-px -translate-x-1/2 -translate-y-1/2 bg-white/70"
              style={{ left: `${tip.x}%` }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function AggregatorHints({
  items,
  grade,
  specialty,
}: {
  items: DonorSalaryRow[];
  grade?: string;
  specialty?: string;
}) {
  const grouped = new Map<string, DonorSalaryRow[]>();
  for (const row of items) {
    const source = row.source || "";
    if (!source) continue;
    grouped.set(source, [...(grouped.get(source) || []), row]);
  }
  const order = ["habr_career", "hh_career", "getmatch_salaries", "levels.fyi"];
  const keys = [...order.filter((key) => grouped.has(key)), ...[...grouped.keys()].filter((key) => !order.includes(key))];
  const fallback: Record<string, string> = {
    habr_career: HABR_SALARIES_URL,
    getmatch_salaries: GETMATCH_SALARIES_URL,
    "levels.fyi": LEVELS_FYI_URL,
    hh_career: "https://career.hh.ru/professions",
  };
  const names: Record<string, string> = {
    habr_career: "хабр карьера",
    hh_career: "hh.ru",
    getmatch_salaries: "getmatch",
    "levels.fyi": "levels.fyi",
  };
  return (
    <>
      {keys.map((source) => (
        <DonorHint
          key={source}
          items={grouped.get(source) || []}
          fallbackUrl={fallback[source] || "#"}
          name={names[source] || source}
          grade={grade}
          specialty={specialty}
          hiKey={source === "getmatch_salaries" ? "p90" : "p75"}
        />
      ))}
    </>
  );
}

function pickDonorRow(
  items: DonorSalaryRow[],
  grade?: string,
  specialty?: string,
): DonorSalaryRow | null {
  if (!items.length) return null;
  if (specialty) {
    const hit = items.find((row) => (row.specialty || "") === specialty);
    if (hit) return hit;
  }
  if (grade) {
    const hit = items.find((row) => (row.grade || "") === grade);
    if (hit) return hit;
  }
  const overall = items.find((row) => !row.grade && !row.specialty);
  if (overall) return overall;
  const graded = items.filter((row) => row.grade);
  if (graded.length === 1) return graded[0];
  return items[0];
}

function DonorHint({
  items,
  fallbackUrl,
  name,
  grade,
  specialty,
  hiKey = "p75",
}: {
  items: DonorSalaryRow[];
  fallbackUrl: string;
  name: string;
  grade?: string;
  specialty?: string;
  hiKey?: "p75" | "p90";
}) {
  const row = pickDonorRow(items, grade, specialty);
  if (!row?.median) return null;
  const hi = hiKey === "p90" ? row.p90 : row.p75;
  const range =
    row.p25 != null && hi != null
      ? `${formatCorridorK(row.p25)}–${formatCorridorK(row.median)}–${formatCorridorK(hi)}`
      : formatCorridorK(row.median);
  const hint = [
    row.grade || row.specialty || "",
    row.n ? `n=${row.n >= 1000 ? `${Math.round(row.n / 1000)}k` : row.n}` : "",
    hiKey === "p90" ? "p90" : "",
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <a
      href={row.url || fallbackUrl}
      target="_blank"
      rel="noreferrer"
      title={hint || undefined}
      className="group flex items-baseline justify-between gap-4 py-1 text-[12px] leading-5"
    >
      <span className="min-w-0 truncate text-muted underline decoration-white/25 underline-offset-2 group-hover:text-accent group-hover:decoration-accent/50">
        {name}
      </span>
      <span className="shrink-0 tabular-nums text-white/80">{range}</span>
    </a>
  );
}

type FilterOpt = { key?: string; label?: string; n: number };

function FilterSelect({
  label,
  value,
  options,
  onChange,
  compact,
}: {
  label: string;
  value: string;
  options: FilterOpt[];
  onChange: (next: string) => void;
  compact?: boolean;
}) {
  if (!options.length) return null;
  return (
    <label className={`flex min-w-0 flex-col gap-1 ${compact ? "text-[11px]" : "text-[12px]"}`}>
      <span className="text-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`max-w-[11rem] truncate border-white/12 bg-[#0e1015] py-1 pl-2 text-white/90 ${
          compact ? "text-[11px]" : "text-[12px]"
        }`}
      >
        <option value="">все</option>
        {options.map((item) => (
          <option key={item.key || item.label} value={item.key || ""}>
            {item.label || item.key}
          </option>
        ))}
      </select>
    </label>
  );
}

function corridorFromAggregators(market: SalaryMarket | null | undefined): SalaryCorridor | null {
  const rows = market?.aggregators?.length
    ? market.aggregators
    : [...(market?.habr_career || []), ...(market?.getmatch || []), ...(market?.hh_career || [])];
  const habr = rows.find(
    (row) => row.source === "habr_career" && !row.grade && row.p25 != null && row.median != null && row.p75 != null,
  );
  if (!habr || habr.p25 == null || habr.median == null || habr.p75 == null) return null;
  return {
    n: habr.n || 1,
    n_vacancies: 0,
    n_aggregators: rows.length,
    p25: habr.p25,
    median: habr.median,
    p75: habr.p75,
    currency: "RUB",
  };
}

function pickCorridor(market: SalaryMarket | null | undefined): SalaryCorridor | null {
  const raw = (market?.market || market?.platforms || null) as SalaryCorridor | null;
  if (raw && raw.p25 != null && raw.median != null && raw.p75 != null) return raw;
  return corridorFromAggregators(market);
}

export function SalaryCorridorBlock({
  huntId,
  threshold,
  compact = false,
}: {
  huntId?: number | null;
  threshold?: number | null;
  compact?: boolean;
}) {
  const [grade, setGrade] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [market, setMarket] = useState<SalaryMarket | null>(null);
  const [busy, setBusy] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(!compact);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!compact || !sourcesOpen) return;
    function onDoc(e: MouseEvent) {
      if (root.current && !root.current.contains(e.target as Node)) setSourcesOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [compact, sourcesOpen]);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    api
      .salaryMarket({
        hunt_id: huntId ?? undefined,
        grade: grade || undefined,
        specialty: specialty || undefined,
      })
      .then((data) => {
        if (!cancelled) setMarket(data);
      })
      .catch(() => {
        if (!cancelled) setMarket(null);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [huntId, grade, specialty]);

  const corridor = pickCorridor(market);
  const grades = market?.filters?.grades || [];
  const specialties = market?.filters?.specialties || [];

  if (!corridor) {
    return (
      <p className={compact ? "text-[12px] text-muted" : "mt-4 text-[13px] text-muted"}>
        {busy ? "считаю рынок…" : "рынок зарплат не загрузился"}
      </p>
    );
  }

  const details = !compact || sourcesOpen;

  return (
    <div ref={root} className={compact ? "relative min-w-0" : "mt-5"}>
      <div className={compact ? "flex items-end gap-3" : undefined}>
        <div className="min-w-0 flex-1">
          <CorridorStrip corridor={corridor} threshold={threshold} compact={compact} busy={busy} />
        </div>
        {compact ? (
          <button
            type="button"
            onClick={() => setSourcesOpen((open) => !open)}
            className="shrink-0 pb-1 text-[12px] text-muted hover:text-white"
          >
            {sourcesOpen ? "свернуть" : "источники"}
          </button>
        ) : null}
      </div>
      {threshold != null && threshold > 0 ? (
        <p className="text-[11px] text-muted">порог {Math.round(threshold / 1000)}к</p>
      ) : null}

      {details ? (
        <div
          className={
            compact
              ? "absolute left-0 top-full z-30 mt-1 w-[min(100%,28rem)] rounded-xl border border-line bg-[#12141b] px-3 py-2.5 shadow-[0_12px_40px_rgba(0,0,0,0.45)]"
              : undefined
          }
        >
          {(grades.length > 0 || specialties.length > 0) && (
            <div className={`flex flex-wrap gap-4 ${compact ? "mt-3" : "mt-4"}`}>
              <FilterSelect
                label="грейд"
                value={grade}
                options={grades}
                onChange={setGrade}
                compact={compact}
              />
              <FilterSelect
                label="специальность"
                value={specialty}
                options={specialties}
                onChange={setSpecialty}
                compact={compact}
              />
            </div>
          )}

          <div className={`${compact ? "mt-3" : "mt-4"} divide-y divide-white/[0.06] border-y border-white/[0.06]`}>
            <AggregatorHints
              items={
                market?.aggregators?.length
                  ? market.aggregators
                  : [...(market?.habr_career || []), ...(market?.getmatch || []), ...(market?.hh_career || [])]
              }
              grade={grade}
              specialty={specialty}
            />
          </div>
          <p className="mt-3 text-[11px] leading-4 text-muted/80">
            перепроверь вилку компании на{" "}
            <a
              href={LEVELS_FYI_URL}
              target="_blank"
              rel="noreferrer"
              className="underline decoration-white/25 underline-offset-2 hover:text-accent hover:decoration-accent/50"
            >
              levels.fyi
            </a>
          </p>
        </div>
      ) : null}
    </div>
  );
}
