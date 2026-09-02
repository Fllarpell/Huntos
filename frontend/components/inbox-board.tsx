"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import type { CollisionItem, Vacancy } from "@/lib/types";
import { MatchBadge } from "./match-badge";
import { VacancyDrawer } from "./vacancy-drawer";
import { CompanyMark } from "./company-mark";
import { SearchField } from "./search-field";
import { ChoiceChips, FilterChips } from "./filter-chips";
import { moneyLabel } from "@/lib/format";
import { RelativeTime } from "./relative-time";
import { FORMATS, LEVELS } from "@/lib/hirehi-filters";
import { NextStepBadge } from "./next-step-badge";
import { CollisionBanner } from "./collision-banner";
import { CustomFieldChips } from "./custom-field-chips";
import { HhPulseMark } from "./hh-pulse-mark";

const SORTS = [
  { value: "best", label: "условия" },
  { value: "recent", label: "новизна" },
  { value: "grade", label: "грейд" },
  { value: "match", label: "совпадение" },
];

const NDA = [
  { value: "any", label: "все компании" },
  { value: "named", label: "не NDA" },
  { value: "nda", label: "NDA" },
];

const SALARY = [
  { value: "any", label: "любая зп" },
  { value: "known", label: "зп указана" },
  { value: "hidden", label: "зп скрыта" },
];

const SOURCES = [
  { value: "hirehi", label: "HireHi" },
  { value: "hh", label: "hh.ru" },
  { value: "telegram", label: "Telegram" },
  { value: "clip", label: "клиппер" },
  { value: "manual", label: "вручную" },
];

const SORT_HINT: Record<string, string> = {
  best: "сверху свежие за сутки, затем зарплата и совпадение с резюме",
  recent: "сверху самые новые",
  grade: "сверху выше грейд",
  match: "сверху лучше совпадение с резюме",
};

export function InboxBoard() {
  const { activeHuntId } = useHunt();
  const [items, setItems] = useState<Vacancy[]>([]);
  const [total, setTotal] = useState(0);
  const [focusId, setFocusId] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [openId, setOpenId] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("best");
  const [grades, setGrades] = useState<string[]>([]);
  const [formats, setFormats] = useState<string[]>([]);
  const [nda, setNda] = useState("any");
  const [salary, setSalary] = useState("any");
  const [sources, setSources] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upcoming, setUpcoming] = useState<CollisionItem[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    const id = Number(new URLSearchParams(window.location.search).get("open"));
    if (Number.isFinite(id) && id > 0) setOpenId(id);
  }, []);

  const load = useCallback(async (opts?: { quiet?: boolean }) => {
    try {
      const data = await api.vacancies({
        stage: "inbox",
        sort,
        q,
        grade: grades,
        format: formats,
        nda,
        salary,
        source: sources,
        hunt_id: activeHuntId,
        limit: 200,
      });
      setItems(data.items);
      setTotal(data.total);
      setChecked((prev) => new Set([...prev].filter((id) => data.items.some((v) => v.id === id))));
      if (!opts?.quiet) {
        const cal = await api.collisions();
        setUpcoming(cal.upcoming);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Нет связи с API");
    } finally {
      setLoading(false);
    }
  }, [q, sort, grades, formats, nda, salary, sources, activeHuntId]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === "visible") void load({ quiet: true });
    }, 60000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    if (focusId == null && items[0]) setFocusId(items[0].id);
  }, [items, focusId]);

  const focusIndex = items.findIndex((v) => v.id === focusId);
  const allChecked = items.length > 0 && items.every((v) => checked.has(v.id));
  const checkedIds = useMemo(() => items.filter((v) => checked.has(v.id)).map((v) => v.id), [items, checked]);

  const move = useCallback(async (ids: number[], stage: "to_apply" | "trash") => {
    if (!ids.length) return;
    try {
      if (ids.length === 1) await api.setStage(ids[0], stage, undefined, activeHuntId);
      else await api.bulkStage(ids, stage, activeHuntId);
      setItems((prev) => prev.filter((v) => !ids.includes(v.id)));
      setTotal((n) => Math.max(0, n - ids.length));
      setChecked((prev) => new Set([...prev].filter((id) => !ids.includes(id))));
      setOpenId((cur) => (cur && ids.includes(cur) ? null : cur));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сдвинуть");
      void load();
    }
  }, [load, activeHuntId]);

  async function addManual() {
    try {
      const created = await api.createVacancy({ title: "Новая вакансия", hunt_id: activeHuntId });
      setItems((prev) => [created, ...prev]);
      setTotal((n) => n + 1);
      setFocusId(created.id);
      setOpenId(created.id);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать");
    }
  }

  function toggleCheck(id: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "j") {
        const next = items[Math.min(items.length - 1, Math.max(0, focusIndex) + 1)];
        if (next) setFocusId(next.id);
      }
      if (e.key === "k") {
        const prev = items[Math.max(0, focusIndex - 1)];
        if (prev) setFocusId(prev.id);
      }
      const current = items[focusIndex];
      if (e.key === " " && current) {
        e.preventDefault();
        toggleCheck(current.id);
      }
      const targets = checkedIds.length ? checkedIds : current ? [current.id] : [];
      if (e.key === "e") void move(targets, "to_apply");
      if (e.key === "x") void move(targets, "trash");
      if (e.key === "Enter" && current) setOpenId(current.id);
      if (e.key === "Escape") setOpenId(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, focusIndex, checkedIds, move]);

  const filterCount =
    grades.length +
    formats.length +
    sources.length +
    (nda !== "any" ? 1 : 0) +
    (salary !== "any" ? 1 : 0);
  const filtersIdle = !q && !filterCount && nda === "any" && salary === "any";

  return (
    <div className="relative flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center gap-x-6 gap-y-3 px-7 pt-6 pb-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight">Inbox</h1>
          <p className="mt-0.5 text-[12px] text-muted">
            {loading ? "…" : `${total}`}
            {q ? " по запросу" : ""}
          </p>
        </div>
        <div className="flex items-center gap-5 text-[13px]">
          {SORTS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setSort(option.value)}
              className={`border-b pb-0.5 ${
                sort === option.value ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
              }`}
              title={SORT_HINT[option.value]}
            >
              {option.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setFiltersOpen((open) => !open)}
          className={`text-[13px] ${filterCount || filtersOpen ? "text-accent" : "text-muted hover:text-white"}`}
        >
          фильтры{filterCount ? ` · ${filterCount}` : ""}
        </button>
        <div className="ml-auto min-w-[200px] max-w-xs flex-1">
          <SearchField
            value={q}
            onChange={setQ}
            placeholder="роль, компания, @hr"
          />
        </div>
        <button
          type="button"
          onClick={() => void addManual()}
          className="inline-flex items-center gap-1.5 text-[13px] text-accent hover:bg-accent/10 rounded-full px-3 py-1.5"
        >
          <Plus size={14} />
          вакансия
        </button>
      </header>

      {filtersOpen && (
        <section className="shrink-0 space-y-2 border-t border-line px-7 py-4">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <span className="w-16 shrink-0 text-[11px] tracking-[0.14em] text-muted uppercase">Грейд</span>
            <FilterChips options={LEVELS} value={grades} onChange={setGrades} />
          </div>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <span className="w-16 shrink-0 text-[11px] tracking-[0.14em] text-muted uppercase">Формат</span>
            <FilterChips options={FORMATS} value={formats} onChange={setFormats} />
          </div>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <span className="w-16 shrink-0 text-[11px] tracking-[0.14em] text-muted uppercase">Ещё</span>
            <ChoiceChips options={NDA} value={nda} onChange={setNda} />
            <ChoiceChips options={SALARY} value={salary} onChange={setSalary} />
            <FilterChips options={SOURCES} value={sources} onChange={setSources} />
          </div>
        </section>
      )}

      <CollisionBanner items={upcoming} onOpen={setOpenId} />

      {error && (
        <p className="mx-7 mb-3 rounded-xl border border-rose-400/20 bg-rose-400/8 px-4 py-2.5 text-sm text-rose-100">
          {error}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto border-t border-line pb-28">
        {loading ? (
          <p className="px-7 py-10 text-[13px] text-muted">Загрузка…</p>
        ) : items.length === 0 ? (
          <div className="px-7 py-16">
            <p className="text-[22px] font-medium tracking-tight">
              {total === 0 && filtersIdle ? "Пока пусто" : "Ничего не нашлось"}
            </p>
            <p className="mt-3 max-w-md text-[14px] leading-6 text-muted">
              {total === 0 && filtersIdle
                ? "Запусти поиск в Настройках — вакансии появятся сюда."
                : "Сними часть фильтров или измени сортировку."}
            </p>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-3 px-7 py-2 text-[11px] tracking-[0.08em] text-muted uppercase">
              <input
                type="checkbox"
                checked={allChecked}
                onChange={() => {
                  if (allChecked) setChecked(new Set());
                  else setChecked(new Set(items.map((v) => v.id)));
                }}
                className="h-4 w-4"
              />
              <span className="w-[200px]">Компания</span>
              <span className="flex-1">Роль</span>
              <span className="w-[132px] text-right">Условия</span>
              <span className="w-10 text-center">Fit</span>
            </div>
            {items.map((v) => {
              const money = moneyLabel(v);
              const focused = v.id === focusId;
              const isChecked = checked.has(v.id);
              const meta = [v.grade, v.work_format].filter(Boolean).join(" · ");
              return (
                <article
                  key={v.id}
                  onClick={() => {
                    setFocusId(v.id);
                    setOpenId(v.id);
                  }}
                  className={`group flex cursor-pointer items-center gap-3 border-l-2 px-7 py-3.5 ${
                    focused ? "border-accent bg-white/[0.03]" : "border-transparent hover:bg-white/[0.02]"
                  } ${isChecked ? "bg-accent/[0.04]" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleCheck(v.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="h-4 w-4 shrink-0 opacity-40 group-hover:opacity-100 checked:opacity-100"
                  />
                  <CompanyMark vacancy={v} size={32} />
                  <div className="min-w-0 w-[200px] shrink-0">
                    <p className="truncate text-[15px] font-medium">{v.company || "без компании"}</p>
                    <p className="truncate text-[12px] text-muted">
                      <RelativeTime iso={v.published_at} />
                    </p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-center gap-2">
                      <h2 className="truncate text-[15px] font-normal leading-5">{v.title}</h2>
                      <NextStepBadge
                        at={v.next_step_at}
                        kind={v.next_step_kind}
                        collide={(v.collision_peers ?? 0) > 1}
                        hint={v.collision_hint}
                      />
                      <HhPulseMark pulse={v.hh_pulse} className="text-[11px]" />
                    </div>
                    <p className="mt-0.5 truncate text-[12px] text-muted">
                      {meta || "без грейда"}
                      {v.source ? ` · ${v.source === "manual" ? "вручную" : v.source}` : ""}
                    </p>
                    <CustomFieldChips bits={v.custom_bits} className="mt-1" />
                  </div>
                  <div className="w-[132px] shrink-0 text-right">
                    <p className={`tabular-nums text-[14px] ${money.known ? "text-white/90" : "text-muted"}`}>
                      {money.text}
                    </p>
                    <div className="mt-1.5 flex justify-end gap-3 opacity-0 transition group-hover:opacity-100">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          void move([v.id], "to_apply");
                        }}
                        className="text-[12px] text-accent"
                      >
                        воронка
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          void move([v.id], "trash");
                        }}
                        className="text-[12px] text-muted hover:text-white"
                      >
                        мусор
                      </button>
                    </div>
                  </div>
                  <div className="w-10 shrink-0 text-center">
                    <MatchBadge score={v.match_score} status={v.scoring_status} size="sm" />
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      {checkedIds.length > 0 && (
        <div className="absolute bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-4 rounded-full border border-line bg-bg-soft/95 px-5 py-2.5 text-[13px] shadow-2xl backdrop-blur">
          <span className="text-muted">{checkedIds.length} выбрано</span>
          <button onClick={() => void move(checkedIds, "to_apply")} className="text-accent">
            В воронку
          </button>
          <button onClick={() => void move(checkedIds, "trash")} className="text-muted hover:text-white">
            Мусор
          </button>
          <button onClick={() => setChecked(new Set())} className="text-muted hover:text-white">
            Снять
          </button>
        </div>
      )}

      {openId != null && (
        <VacancyDrawer
          vacancyId={openId}
          onClose={() => {
            setOpenId(null);
            void api.collisions().then((cal) => setUpcoming(cal.upcoming)).catch(() => undefined);
          }}
          onChanged={(fresh) => {
            setItems((prev) => prev.map((v) => (v.id === fresh.id ? { ...v, ...fresh } : v)));
          }}
        />
      )}
    </div>
  );
}
