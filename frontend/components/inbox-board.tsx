"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import type { CollisionItem, ScraperConfig, Vacancy } from "@/lib/types";
import { GuideHint, GuideSpot } from "./guide";
import { VacancyDrawer } from "./vacancy-drawer";
import { CompanyMark } from "./company-mark";
import { SearchField } from "./search-field";
import { ChoiceChips, FilterChips, OverflowFilterChips } from "./filter-chips";
import { CompanyExcludeInput } from "./company-exclude-input";
import { moneyLabel } from "@/lib/format";
import { SalaryCorridorBlock } from "./salary-corridor";
import { RelativeTime } from "./relative-time";
import { FORMATS, LEVELS } from "@/lib/hirehi-filters";
import { SEARCH_STACK } from "@/lib/hunt-search";
import { extraSourcesLine, sourceLabel } from "@/components/source-badge";
import { NextStepBadge } from "./next-step-badge";
import { CollisionBanner } from "./collision-banner";
import { CustomFieldChips } from "./custom-field-chips";
import { HhPulseMark } from "./hh-pulse-mark";

const SORTS = [
  { value: "best", label: "условия" },
  { value: "recent", label: "новизна" },
  { value: "grade", label: "грейд" },
];

const NDA = [
  { value: "any", label: "все" },
  { value: "named", label: "не NDA" },
  { value: "nda", label: "NDA" },
];

const SALARY = [
  { value: "any", label: "любая" },
  { value: "known", label: "указана" },
  { value: "hidden", label: "скрыта" },
];

const SOURCES = [
  { value: "hirehi", label: "HireHi" },
  { value: "hh", label: "hh.ru" },
  { value: "habr", label: "Habr Career" },
  { value: "getmatch", label: "GetMatch" },
  { value: "geekjob", label: "GeekJob" },
  { value: "career", label: "Компании" },
  { value: "telegram", label: "Telegram" },
  { value: "clip", label: "клиппер" },
  { value: "manual", label: "вручную" },
];

const SORT_HINT: Record<string, string> = {
  best: "сверху свежие за сутки, затем зарплата",
  recent: "сверху самые новые",
  grade: "сверху выше грейд",
};

const NOISE_BITS = new Set(["весь it", "весь it по россии", "все специальности", "все форматы"]);

function inboxSearchLabel(name: string, source?: string) {
  const bits = name
    .split(" · ")
    .map((bit) => bit.trim())
    .filter((bit) => bit && !NOISE_BITS.has(bit.toLowerCase()));
  return bits.join(" · ") || sourceLabel(source) || name;
}

function FilterRow({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <GuideSpot id={id} className="grid grid-cols-[3.75rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1">
      <span className="inline-flex items-center gap-0.5 pt-0.5 text-[10px] tracking-[0.12em] text-muted uppercase">
        {label}
        <GuideHint id={id} />
      </span>
      <div className="min-w-0">{children}</div>
    </GuideSpot>
  );
}

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
  const [stacks, setStacks] = useState<string[]>([]);
  const [searchIds, setSearchIds] = useState<string[]>([]);
  const [configs, setConfigs] = useState<ScraperConfig[]>([]);
  const [excludeCompanies, setExcludeCompanies] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upcoming, setUpcoming] = useState<CollisionItem[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    const id = Number(new URLSearchParams(window.location.search).get("open"));
    if (Number.isFinite(id) && id > 0) setOpenId(id);
  }, []);

  useEffect(() => {
    if (!filtersOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setFiltersOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtersOpen]);

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
        stack: stacks,
        search_id: searchIds.map(Number).filter((id) => id > 0),
        exclude_company: excludeCompanies,
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
  }, [q, sort, grades, formats, nda, salary, sources, stacks, searchIds, excludeCompanies, activeHuntId]);

  useEffect(() => {
    void api.configs().then(setConfigs).catch(() => undefined);
  }, []);

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
    stacks.length +
    searchIds.length +
    (nda !== "any" ? 1 : 0) +
    (salary !== "any" ? 1 : 0) +
    excludeCompanies.length;
  const filtersIdle = !q && !filterCount && nda === "any" && salary === "any";
  const searchOptions = useMemo(() => {
    const aggregators = configs.filter((item) => item.source !== "career");
    const career = configs.filter((item) => item.source === "career");
    return [...aggregators, ...career].map((item) => ({
      value: String(item.id),
      label: inboxSearchLabel(item.name, item.source),
    }));
  }, [configs]);
  const activeChips = useMemo(() => {
    const chips: { key: string; label: string; clear: () => void }[] = [];
    for (const option of LEVELS) {
      if (grades.includes(option.value)) {
        chips.push({
          key: `grade:${option.value}`,
          label: option.label,
          clear: () => setGrades((prev) => prev.filter((item) => item !== option.value)),
        });
      }
    }
    for (const option of FORMATS) {
      if (formats.includes(option.value)) {
        chips.push({
          key: `format:${option.value}`,
          label: option.label,
          clear: () => setFormats((prev) => prev.filter((item) => item !== option.value)),
        });
      }
    }
    if (nda !== "any") {
      const option = NDA.find((item) => item.value === nda);
      chips.push({ key: "nda", label: option?.label || nda, clear: () => setNda("any") });
    }
    if (salary !== "any") {
      const option = SALARY.find((item) => item.value === salary);
      chips.push({ key: "salary", label: `зп ${option?.label || salary}`, clear: () => setSalary("any") });
    }
    for (const option of SOURCES) {
      if (sources.includes(option.value)) {
        chips.push({
          key: `source:${option.value}`,
          label: option.label,
          clear: () => setSources((prev) => prev.filter((item) => item !== option.value)),
        });
      }
    }
    for (const option of searchOptions) {
      if (searchIds.includes(option.value)) {
        chips.push({
          key: `search:${option.value}`,
          label: option.label,
          clear: () => setSearchIds((prev) => prev.filter((item) => item !== option.value)),
        });
      }
    }
    for (const option of SEARCH_STACK) {
      if (stacks.includes(option.value)) {
        chips.push({
          key: `stack:${option.value}`,
          label: option.label,
          clear: () => setStacks((prev) => prev.filter((item) => item !== option.value)),
        });
      }
    }
    for (const name of excludeCompanies) {
      chips.push({
        key: `ex:${name}`,
        label: `кроме ${name}`,
        clear: () => setExcludeCompanies((prev) => prev.filter((item) => item !== name)),
      });
    }
    return chips;
  }, [grades, formats, nda, salary, sources, searchIds, searchOptions, stacks, excludeCompanies]);

  function clearFilters() {
    setGrades([]);
    setFormats([]);
    setNda("any");
    setSalary("any");
    setSources([]);
    setStacks([]);
    setSearchIds([]);
    setExcludeCompanies([]);
  }

  return (
    <div className="relative flex h-screen flex-col overflow-hidden">
      <header className="shrink-0 px-6 pt-4 pb-2">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <GuideSpot id="inbox.header" className="min-w-0 shrink-0">
            <div className="flex items-baseline gap-2">
              <h1 className="text-[20px] font-semibold tracking-tight">Inbox</h1>
              <GuideHint id="inbox.header" />
              <p className="text-[12px] text-muted">{loading ? "…" : total}{q ? " по запросу" : ""}</p>
            </div>
          </GuideSpot>
          <GuideSpot id="inbox.sort">
            <div className="flex items-center gap-4 text-[13px]">
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
              <GuideHint id="inbox.sort" />
            </div>
          </GuideSpot>
          <GuideSpot id="inbox.filters">
            <span className="inline-flex items-center gap-1">
              <button
                type="button"
                onClick={() => setFiltersOpen((open) => !open)}
                className={`text-[13px] ${filterCount || filtersOpen ? "text-accent" : "text-muted hover:text-white"}`}
              >
                {filtersOpen ? "закрыть" : "фильтры"}
                {filterCount ? ` · ${filterCount}` : ""}
              </button>
              <GuideHint id="inbox.filters" />
            </span>
          </GuideSpot>
          <GuideSpot id="inbox.search" className="ml-auto flex min-w-[180px] max-w-xs flex-1 items-center gap-1">
            <SearchField
              className="min-w-0 flex-1 !py-1"
              value={q}
              onChange={setQ}
              placeholder="go, frontend, компания"
            />
            <GuideHint id="inbox.search" />
          </GuideSpot>
          <GuideSpot id="inbox.add">
            <span className="inline-flex items-center gap-1">
              <button
                type="button"
                onClick={() => void addManual()}
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] text-accent hover:bg-accent/10"
              >
                <Plus size={14} />
                вакансия
              </button>
              <GuideHint id="inbox.add" />
            </span>
          </GuideSpot>
        </div>
        {!loading ? (
          <GuideSpot id="inbox.corridor" className="mt-2 max-w-xl">
            <SalaryCorridorBlock huntId={activeHuntId} compact />
          </GuideSpot>
        ) : null}
      </header>

      {!filtersOpen && activeChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-6 pb-2">
          {activeChips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={chip.clear}
              className="rounded-full border border-accent/40 bg-accent/12 px-2.5 py-0.5 text-[12px] text-accent hover:bg-accent/20"
            >
              {chip.label}
              <span className="ml-1 text-accent/70">×</span>
            </button>
          ))}
          <button type="button" onClick={clearFilters} className="px-1 text-[12px] text-muted hover:text-white">
            сбросить
          </button>
        </div>
      )}

      <CollisionBanner items={upcoming} onOpen={setOpenId} />

      {error && (
        <p className="mx-6 mb-2 rounded-xl border border-rose-400/20 bg-rose-400/8 px-4 py-2 text-sm text-rose-100">
          {error}
        </p>
      )}

      <div className="relative min-h-0 flex-1">
        {filtersOpen && (
          <button
            type="button"
            aria-label="закрыть фильтры"
            onClick={() => setFiltersOpen(false)}
            className="absolute inset-0 z-10 bg-black/25"
          />
        )}
        {filtersOpen && (
          <section className="absolute inset-x-0 top-0 z-20 max-h-[min(42vh,320px)] space-y-2 overflow-y-auto border-b border-line bg-[#12141b] px-6 py-3 shadow-[0_12px_40px_rgba(0,0,0,0.45)]">
            {filterCount > 0 ? (
              <div className="flex justify-end">
                <button type="button" onClick={clearFilters} className="text-[12px] text-muted hover:text-white">
                  сбросить все
                </button>
              </div>
            ) : null}
            <FilterRow id="inbox.grade" label="Грейд">
              <FilterChips options={LEVELS} value={grades} onChange={setGrades} variant="chip" />
            </FilterRow>
            <FilterRow id="inbox.format" label="Формат">
              <FilterChips options={FORMATS} value={formats} onChange={setFormats} variant="chip" />
            </FilterRow>
            <GuideSpot id="inbox.more" className="space-y-2">
              <div className="grid grid-cols-[3.75rem_minmax(0,1fr)] items-start gap-x-3">
                <span className="inline-flex items-center gap-0.5 pt-0.5 text-[10px] tracking-[0.12em] text-muted uppercase">
                  Компании
                  <GuideHint id="inbox.more" />
                </span>
                <ChoiceChips options={NDA} value={nda} onChange={setNda} variant="chip" />
              </div>
              <div className="grid grid-cols-[3.75rem_minmax(0,1fr)] items-start gap-x-3">
                <span className="pt-0.5 text-[10px] tracking-[0.12em] text-muted uppercase">Зарплата</span>
                <ChoiceChips options={SALARY} value={salary} onChange={setSalary} variant="chip" />
              </div>
              <div className="grid grid-cols-[3.75rem_minmax(0,1fr)] items-start gap-x-3">
                <span className="pt-0.5 text-[10px] tracking-[0.12em] text-muted uppercase">Откуда</span>
                <FilterChips options={SOURCES} value={sources} onChange={setSources} variant="chip" />
              </div>
            </GuideSpot>
            {searchOptions.length > 0 && (
              <FilterRow id="inbox.searches" label="Поиск">
                <OverflowFilterChips
                  options={searchOptions}
                  value={searchIds}
                  onChange={setSearchIds}
                  preview={6}
                  searchPlaceholder="авиасейлс, hh…"
                />
              </FilterRow>
            )}
            <FilterRow id="inbox.stack" label="Стек">
              <OverflowFilterChips options={SEARCH_STACK} value={stacks} onChange={setStacks} preview={8} />
            </FilterRow>
            <FilterRow id="inbox.except" label="Кроме">
              <div className="max-w-md rounded-full border border-white/10 bg-white/[0.03] px-3 py-1">
                <CompanyExcludeInput value={excludeCompanies} onChange={setExcludeCompanies} />
              </div>
            </FilterRow>
          </section>
        )}

      <div className="h-full overflow-y-auto border-t border-line pb-28">
        <GuideSpot id="inbox.list" className="min-h-full">
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
            </div>
            {items.map((v) => {
              const money = moneyLabel(v);
              const focused = v.id === focusId;
              const isChecked = checked.has(v.id);
              const extras = extraSourcesLine(v);
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
                      {v.source ? ` · ${v.source === "manual" ? "вручную" : sourceLabel(v.source) || v.source}` : ""}
                      {v.searches?.length
                        ? ` · ${v.searches.map((item) => item.name).filter(Boolean).slice(0, 2).join(" · ")}`
                        : ""}
                      {extras ? ` · ${extras}` : ""}
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
                </article>
              );
            })}
          </div>
        )}
        </GuideSpot>
      </div>
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
            if (fresh.pipeline_stage !== "inbox") {
              setItems((prev) => prev.filter((v) => v.id !== fresh.id));
              setTotal((n) => Math.max(0, n - 1));
              setChecked((prev) => {
                if (!prev.has(fresh.id)) return prev;
                const next = new Set(prev);
                next.delete(fresh.id);
                return next;
              });
              return;
            }
            setItems((prev) => prev.map((v) => (v.id === fresh.id ? { ...v, ...fresh } : v)));
          }}
        />
      )}
    </div>
  );
}
