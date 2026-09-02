"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import {
  adjacentStage,
  KANBAN,
  STAGE_LABEL,
  type CollisionItem,
  type NudgeOut,
  type PipelineStage,
  type Vacancy,
} from "@/lib/types";
import { MatchBadge } from "./match-badge";
import { VacancyDrawer } from "./vacancy-drawer";
import { CompanyMark } from "./company-mark";
import { SearchField } from "./search-field";
import { dwellShort, dwellStage, moneyLabel, notePreview, telegramHandle, vacancyTelegramUrl } from "@/lib/format";
import { NextStepBadge } from "./next-step-badge";
import { CollisionBanner } from "./collision-banner";
import { CustomFieldChips } from "./custom-field-chips";
import { NudgeQueue } from "./nudge-queue";
import { HhPulseMark } from "./hh-pulse-mark";

function matchesQuery(v: Vacancy, q: string): boolean {
  if (!q) return true;
  const handle = telegramHandle(v.telegram_alias);
  const hay = [
    v.company,
    v.title,
    v.notes,
    v.grade,
    v.work_format,
    v.telegram_alias,
    handle,
    v.telegram_url,
    v.contact_email,
    v.contact_phone,
    vacancyTelegramUrl(v),
    v.source_url,
    ...(v.skills || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((token) => hay.includes(token.replace(/^@/, "")) || hay.includes(token));
}

function HuntMass({ columns }: { columns: Record<PipelineStage, Vacancy[]> }) {
  const parts = KANBAN.map((col) => ({
    ...col,
    n: columns[col.stage].length,
    due: col.stage === "waiting" ? columns[col.stage].filter((v) => v.ping_due).length : 0,
  }));
  const max = Math.max(1, ...parts.map((p) => p.n));
  return (
    <div className="flex items-end gap-1 px-7 pb-1">
      {parts.map((p) => (
        <div key={p.stage} className="min-w-0 flex-1">
          <p className="mb-1 text-right text-[11px] tabular-nums text-muted">{p.n || ""}</p>
          <div
            className={`w-full rounded-sm ${
              p.due ? "bg-amber-400/55" : p.n ? "bg-accent/45" : "bg-white/8"
            }`}
            style={{ height: `${Math.max(p.n ? 8 : 3, (p.n / max) * 48)}px` }}
            title={`${p.label}: ${p.n}${p.due ? ` · ${p.due} пинг` : ""}`}
          />
        </div>
      ))}
    </div>
  );
}

function PipelineCard({
  v,
  active,
  lane,
  onOpen,
  onMove,
  onDragEnd,
}: {
  v: Vacancy;
  active: boolean;
  lane?: string;
  onOpen: () => void;
  onMove: (stage: PipelineStage) => void;
  onDragEnd?: () => void;
}) {
  const money = moneyLabel(v);
  const note = notePreview(v.notes, 72);
  const left = adjacentStage(v.pipeline_stage, -1);
  const right = adjacentStage(v.pipeline_stage, 1);
  const dwell = dwellStage(v.pipeline_stage) ? dwellShort(v.dwell_days) : "";
  const dragged = useRef(false);

  return (
    <article
      draggable
      onDragStart={(e) => {
        dragged.current = true;
        e.dataTransfer.setData("text/plain", String(v.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragEnd={() => {
        onDragEnd?.();
        window.setTimeout(() => {
          dragged.current = false;
        }, 0);
      }}
      onClick={() => {
        if (dragged.current) return;
        onOpen();
      }}
      className={`group cursor-grab border-l-2 px-3 py-2.5 active:cursor-grabbing ${
        v.hh_pulse === "discarded"
          ? "border-rose-400/80"
          : v.hh_pulse === "invited"
            ? "border-emerald-400/70"
            : v.ping_due
              ? "border-amber-400/80"
              : active
                ? "border-accent bg-white/[0.04]"
                : "border-transparent hover:bg-white/[0.03]"
      }`}
    >
      <div className="flex items-start gap-2.5">
        <CompanyMark vacancy={v} size={28} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <p className="truncate text-[14px] font-medium leading-4">{v.company || "без компании"}</p>
            <MatchBadge score={v.match_score} status={v.scoring_status} size="sm" />
          </div>
          <p className="mt-0.5 truncate text-[13px] text-white/70">{v.title}</p>
          <p className="mt-1 truncate text-[12px] text-muted">
            {lane ? `${lane} · ` : ""}
            <span className={money.known ? "text-white/80" : ""}>{money.text}</span>
            {v.grade ? ` · ${v.grade}` : ""}
          </p>
          {(v.ping_due || v.next_step_at || dwell || v.hh_pulse) && (
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {dwell && (
                <span className={`text-[11px] tabular-nums ${v.dwell_stale ? "text-amber-200" : "text-muted"}`}>
                  {dwell}
                </span>
              )}
              <HhPulseMark pulse={v.hh_pulse} className="text-[11px]" />
              {v.ping_due && (
                <span className="text-[11px] tabular-nums text-amber-200">пинг {v.silence_days ?? 5}д</span>
              )}
              {v.next_step_at && (
                <NextStepBadge
                  at={v.next_step_at}
                  kind={v.next_step_kind}
                  collide={(v.collision_peers ?? 0) > 1}
                  hint={v.collision_hint}
                />
              )}
            </div>
          )}
          {note ? <p className="mt-1 line-clamp-1 text-[12px] text-white/40">{note}</p> : null}
          <CustomFieldChips bits={v.custom_bits} className="mt-1" />
        </div>
      </div>
      <div className="mt-1.5 flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
        <button
          type="button"
          title={left ? `← ${STAGE_LABEL[left]}` : undefined}
          disabled={!left}
          onClick={(e) => {
            e.stopPropagation();
            if (left) onMove(left);
          }}
          className="flex h-6 w-6 items-center justify-center text-muted hover:text-white disabled:opacity-20"
        >
          <ChevronLeft size={14} />
        </button>
        <button
          type="button"
          title={right ? `${STAGE_LABEL[right]} →` : undefined}
          disabled={!right}
          onClick={(e) => {
            e.stopPropagation();
            if (right) onMove(right);
          }}
          className="flex h-6 w-6 items-center justify-center text-muted hover:text-white disabled:opacity-20"
        >
          <ChevronRight size={14} />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onMove("inbox");
          }}
          className="ml-auto text-[11px] text-muted hover:text-white"
        >
          inbox
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onMove("rejected");
          }}
          className="text-[11px] text-rose-200/70 hover:text-rose-100"
        >
          отказ
        </button>
      </div>
    </article>
  );
}

export function KanbanBoard() {
  const { activeHuntId } = useHunt();
  const [columns, setColumns] = useState<Record<PipelineStage, Vacancy[]>>({
    inbox: [],
    to_apply: [],
    waiting: [],
    screening: [],
    interview: [],
    offer: [],
    rejected: [],
    trash: [],
  });
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [hit, setHit] = useState(0);
  const [upcoming, setUpcoming] = useState<CollisionItem[]>([]);
  const [nudge, setNudge] = useState<NudgeOut | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const [dropStage, setDropStage] = useState<PipelineStage | null>(null);

  async function load() {
    try {
      const [data, cal, ping] = await Promise.all([
        api.pipeline(activeHuntId),
        api.collisions(),
        api.nudge(activeHuntId),
      ]);
      setColumns((prev) => {
        const next = { ...prev };
        for (const col of KANBAN) next[col.stage] = [];
        for (const col of data) next[col.stage] = col.items;
        return next;
      });
      setUpcoming(cal.upcoming);
      setNudge(ping);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }

  function applyVacancy(fresh: Vacancy) {
    setColumns((prev) => {
      const next = { ...prev };
      const from = (Object.keys(prev) as PipelineStage[]).find((stage) => prev[stage].some((v) => v.id === fresh.id)) ?? null;
      const to = fresh.pipeline_stage;
      if (from && from === to) {
        next[from] = prev[from].map((v) => (v.id === fresh.id ? { ...v, ...fresh } : v));
        return next;
      }
      if (from) next[from] = prev[from].filter((v) => v.id !== fresh.id);
      if (to in next) next[to] = [...next[to], fresh];
      return next;
    });
  }

  useEffect(() => {
    void load();
  }, [activeHuntId]);

  const all = useMemo(
    () => KANBAN.flatMap((col) => columns[col.stage].map((v) => ({ v, stage: col.stage }))),
    [columns],
  );
  const hits = useMemo(() => all.filter(({ v }) => matchesQuery(v, q)), [all, q]);
  const searching = q.trim().length > 0;
  const focused = hits[Math.min(hit, Math.max(0, hits.length - 1))] ?? null;
  const live = all.filter(({ stage }) => stage !== "rejected").length;

  useEffect(() => {
    setHit(0);
  }, [q]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      const inField = tag === "INPUT" || tag === "TEXTAREA";
      if ((e.key === "/" || (e.metaKey && e.key.toLowerCase() === "k")) && !inField) {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
        return;
      }
      if (e.key === "Escape") {
        if (document.activeElement === searchRef.current && q) {
          setQ("");
          return;
        }
        searchRef.current?.blur();
        setOpenId(null);
        return;
      }
      if (!searching) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHit((i) => Math.min(hits.length - 1, i + 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHit((i) => Math.max(0, i - 1));
      }
      if (e.key === "Enter" && focused) {
        e.preventDefault();
        setOpenId(focused.v.id);
      }
      if ((e.key === "r" || e.key === "R") && focused && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        void moveTo(focused.v.id, "rejected");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searching, hits.length, focused, q]);

  async function moveTo(id: number, stage: PipelineStage) {
    const fromStage = (Object.keys(columns) as PipelineStage[]).find((key) =>
      columns[key].some((v) => v.id === id),
    );
    if (!fromStage || fromStage === stage) return;
    const card = columns[fromStage].find((v) => v.id === id);
    if (!card) return;
    setColumns({
      ...columns,
      [fromStage]: columns[fromStage].filter((v) => v.id !== id),
      [stage]: [{ ...card, pipeline_stage: stage, dwell_days: 0, dwell_stale: false }, ...columns[stage]],
    });
    try {
      await api.setStage(id, stage, undefined, activeHuntId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сдвинулось");
    }
    void load();
  }

  async function dropOn(stage: PipelineStage, id: number) {
    await moveTo(id, stage);
  }

  async function addManual() {
    try {
      const created = await api.createVacancy({
        title: "Новая вакансия",
        pipeline_stage: "to_apply",
        hunt_id: activeHuntId,
      });
      setOpenId(created.id);
      await load();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать");
    }
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center gap-x-6 gap-y-3 px-7 pt-6 pb-3">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight">Воронка</h1>
          <p className="mt-0.5 text-[12px] text-muted">
            {live} в охоте
            <span className="text-white/20"> · </span>
            <span className="kbd">/</span> поиск
          </p>
        </div>
        <div className="ml-auto min-w-[200px] max-w-xs flex-1">
          <SearchField
            inputRef={searchRef}
            value={q}
            onChange={setQ}
            placeholder="компания, роль, @hr"
          />
        </div>
        <button
          type="button"
          onClick={() => void addManual()}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-accent hover:bg-accent/10"
        >
          <Plus size={14} />
          вакансия
        </button>
      </header>

      {!searching && <HuntMass columns={columns} />}

      {error && <p className="px-7 pb-2 text-sm text-rose-200">{error}</p>}
      <CollisionBanner items={upcoming} onOpen={setOpenId} />
      {nudge && nudge.total > 0 && (
        <NudgeQueue
          afterDays={nudge.after_days}
          groups={nudge.groups}
          calendarConnected={nudge.calendar_connected}
          onOpen={setOpenId}
          onChanged={() => void load()}
        />
      )}

      {searching ? (
        <div className="min-h-0 flex-1 overflow-y-auto border-t border-line">
          {hits.length === 0 ? (
            <div className="px-7 py-16">
              <p className="text-[22px] font-medium tracking-tight">Никого не нашёл</p>
              <p className="mt-3 text-[14px] text-muted">Другой запрос или Escape, чтобы сбросить.</p>
            </div>
          ) : (
            hits.map((row, i) => (
              <PipelineCard
                key={row.v.id}
                v={row.v}
                active={i === hit}
                lane={STAGE_LABEL[row.stage]}
                onOpen={() => setOpenId(row.v.id)}
                onMove={(stage) => void moveTo(row.v.id, stage)}
              />
            ))
          )}
        </div>
      ) : (
        <div
          ref={boardRef}
          className="flex min-h-0 flex-1 overflow-x-auto border-t border-line"
          onDragOver={(e) => {
            const el = boardRef.current;
            if (!el) return;
            const rect = el.getBoundingClientRect();
            if (e.clientX > rect.right - 72) el.scrollLeft += 28;
            if (e.clientX < rect.left + 72) el.scrollLeft -= 28;
          }}
        >
          {KANBAN.map((col) => {
            const raw = columns[col.stage];
            const visible =
              col.stage === "waiting"
                ? [...raw].sort(
                    (a, b) =>
                      Number(Boolean(b.ping_due)) - Number(Boolean(a.ping_due)) ||
                      (b.silence_days ?? 0) - (a.silence_days ?? 0),
                  )
                : raw;
            const dueCount = col.stage === "waiting" ? raw.filter((v) => v.ping_due).length : 0;
            const wide = col.stage === "waiting";
            return (
              <section
                key={col.stage}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDropStage(col.stage);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDropStage(null);
                  const id = Number(e.dataTransfer.getData("text/plain"));
                  if (id) void dropOn(col.stage, id);
                }}
                className={`flex shrink-0 flex-col border-r border-line last:border-r-0 ${
                  wide ? "w-[320px]" : "w-[240px]"
                } ${dropStage === col.stage ? "bg-accent/[0.06]" : ""}`}
              >
                <div className="px-4 py-3">
                  <p className="text-[11px] tracking-[0.14em] text-muted uppercase">{col.label}</p>
                  <p className="mt-1 text-[15px] tabular-nums">
                    {visible.length}
                    {dueCount > 0 && <span className="ml-2 text-[12px] text-amber-200">{dueCount} пинг</span>}
                  </p>
                </div>
                <div className="flex min-h-0 flex-1 flex-col overflow-y-auto pb-6">
                  {visible.map((v) => (
                    <PipelineCard
                      key={v.id}
                      v={v}
                      active={focused?.v.id === v.id}
                      onOpen={() => setOpenId(v.id)}
                      onMove={(stage) => void moveTo(v.id, stage)}
                      onDragEnd={() => setDropStage(null)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {openId != null && (
        <VacancyDrawer
          vacancyId={openId}
          onClose={() => {
            setOpenId(null);
            void load();
          }}
          onChanged={applyVacancy}
        />
      )}
    </div>
  );
}
