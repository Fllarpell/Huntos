"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { ChoiceChips, CityPicker, FilterChips } from "@/components/filter-chips";
import { SearchSourceSheet } from "@/components/search-source-sheet";
import { SourceBadge, sourceLabel } from "@/components/source-badge";
import { SourceSwitchRow, Switch } from "@/components/source-switch";
import { GuideHint, GuideLabel, GuideSpot } from "@/components/guide";
import { relativeTime } from "@/lib/format";
import {
  EMPTY_HUNT_SEARCH,
  SEARCH_FORMATS,
  SEARCH_LEVELS,
  SEARCH_SALARIES,
  SEARCH_STACK_GROUPS,
  configCoversPick,
  draftFromConfig,
  payloadForPick,
  pickKeyFromConfig,
  maxPagesForSource,
  type HuntSearch,
} from "@/lib/hunt-search";
import type { CareerBoard, DonorCrawl, ScraperConfig } from "@/lib/types";

const AGGREGATORS = [
  { value: "hirehi", label: "HireHi", hint: "", color: "#7dd3c7" },
  { value: "hh", label: "hh.ru", hint: "", color: "#ed4d4d" },
  { value: "habr", label: "Habr Career", hint: "", color: "#6ea8ff" },
  { value: "getmatch", label: "GetMatch", hint: "", color: "#a78bfa" },
  { value: "geekjob", label: "GeekJob", hint: "", color: "#5ee0c8" },
] as const;

const BOARD_COLORS: Record<string, string> = {
  aviasales: "#5ee0a8",
  avito: "#9fd4ff",
  kaspersky: "#7d9bff",
  tbank: "#ffd36a",
  vk: "#4c8dff",
  yandex: "#e7c36a",
  yadro: "#7ec8e8",
  megafon: "#5ee0a8",
  solar: "#f0a36b",
  selectel: "#7dd3c7",
  x5: "#ff8a65",
  itone: "#5ee0c8",
  cloudru: "#7ec8e8",
  croc: "#57e15e",
  jet: "#00c3ff",
  mts: "#ff0032",
  ibs: "#0066cc",
  "2gis": "#27ae60",
  alfa: "#ef3124",
  kontur: "#366fed",
  wb: "#a73afd",
  ozon: "#005bff",
};

const DEFAULT_PICKS = AGGREGATORS.map((item) => item.value);

type SearchView = "list" | "compose" | "pool";

function careerPick(slug: string) {
  return `career:${slug}`;
}

function pickLabel(key: string, boards: CareerBoard[]) {
  if (key.startsWith("career:")) {
    const slug = key.slice("career:".length);
    return boards.find((board) => board.slug === slug)?.name || slug;
  }
  return AGGREGATORS.find((item) => item.value === key)?.label || sourceLabel(key);
}

function BoardPickList({
  boards,
  picked,
  editingId,
  alreadyHas,
  onToggle,
}: {
  boards: CareerBoard[];
  picked: string[];
  editingId: number | null;
  alreadyHas: (key: string) => boolean;
  onToggle: (key: string, on: boolean) => void;
}) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const selected = new Set(picked.filter((key) => key.startsWith("career:")));
  const filtered = boards.filter((board) => {
    if (!needle) return true;
    return board.name.toLowerCase().includes(needle) || board.slug.toLowerCase().includes(needle);
  });
  const ordered = needle
    ? filtered
    : [...filtered.filter((board) => selected.has(careerPick(board.slug))), ...filtered.filter((board) => !selected.has(careerPick(board.slug)))];

  return (
    <div className="space-y-2 pb-1">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Яндекс, VK, Т-Банк…" className="w-full" />
      <div className="max-h-[280px] overflow-y-auto">
        {ordered.length === 0 ? <p className="py-3 text-[13px] text-muted">нет такой доски</p> : null}
        {ordered.map((board) => {
          const key = careerPick(board.slug);
          const covered = editingId == null && alreadyHas(key);
          const on = picked.includes(key);
          return (
            <div key={key} className="flex items-center gap-3 border-b border-white/[0.08] py-2">
              {board.logo_url ? (
                <img
                  src={board.logo_url}
                  alt=""
                  width={22}
                  height={22}
                  className="h-[22px] w-[22px] shrink-0 rounded-md bg-white/8 object-contain"
                />
              ) : (
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: BOARD_COLORS[board.slug] || "#8b909d" }}
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] leading-5">{board.name}</p>
                {covered ? <p className="text-[12px] text-muted">уже качает этот поиск</p> : null}
              </div>
              <Switch
                on={on}
                onChange={(next) => onToggle(key, next)}
                disabled={editingId != null && picked[0] !== key}
                label={board.name}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function configRunLine(config: ScraperConfig, runningNow: boolean): { text: string; tone: "ok" | "err" | "run" | "idle" } {
  if (runningNow || config.last_run?.status === "running" || config.last_run?.status === "queued") {
    return {
      text: config.last_run?.status === "queued" ? "в очереди" : "ищет…",
      tone: "run",
    };
  }
  if (!config.enabled) return { text: "выключен", tone: "idle" };
  const last = config.last_run;
  if (!last) return { text: "ещё не запускался", tone: "idle" };
  if (last.status === "error") return { text: last.error || "ошибка прогона", tone: "err" };
  const when = relativeTime(last.finished_at || last.started_at) || "только что";
  return { text: `${when} · ${last.found_count} найдено · ${last.new_count} новых`, tone: "ok" };
}

export function SearchesSettings({
  isHost,
  onStatus,
  onError,
}: {
  isHost: boolean;
  onStatus: (text: string | null) => void;
  onError: (text: string | null) => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<SearchView>("list");
  const [boardsOpen, setBoardsOpen] = useState(false);
  const [configs, setConfigs] = useState<ScraperConfig[]>([]);
  const [crawls, setCrawls] = useState<DonorCrawl[]>([]);
  const [boards, setBoards] = useState<CareerBoard[]>([]);
  const [picked, setPicked] = useState<string[]>(DEFAULT_PICKS);
  const [draft, setDraft] = useState<HuntSearch>(EMPTY_HUNT_SEARCH);
  const [sheetKey, setSheetKey] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [runningIds, setRunningIds] = useState<Set<number>>(new Set());

  async function refreshCrawls() {
    if (!isHost) {
      setCrawls([]);
      return;
    }
    try {
      setCrawls(await api.crawls());
    } catch {
      setCrawls([]);
    }
  }

  async function load() {
    const list = await api.configs();
    setConfigs(list);
    await refreshCrawls();
    try {
      setBoards(await api.boards());
    } catch {
      setBoards([]);
    }
  }

  async function loadStatus() {
    const list = await api.configs();
    setConfigs(list);
    setRunningIds((prev) => {
      const next = new Set(prev);
      for (const config of list) {
        if (config.last_run && config.last_run.status !== "running" && config.last_run.status !== "queued") {
          next.delete(config.id);
        }
      }
      return next;
    });
    await refreshCrawls();
  }

  useEffect(() => {
    load().catch((e) => onError(e instanceof Error ? e.message : "Ошибка"));
  }, [isHost]);

  useEffect(() => {
    if (!isHost && view === "pool") setView("list");
  }, [isHost, view]);

  useEffect(() => {
    const scroller = rootRef.current?.closest(".overflow-y-auto");
    scroller?.scrollTo({ top: 0 });
  }, [view]);

  const anyRunning =
    runningIds.size > 0 ||
    configs.some((c) => c.last_run?.status === "running" || c.last_run?.status === "queued") ||
    crawls.some((row) => row.queue_status === "pending" || row.queue_status === "running");

  useEffect(() => {
    const ms = anyRunning ? 2000 : 15000;
    const timer = window.setInterval(() => {
      void loadStatus();
    }, ms);
    return () => window.clearInterval(timer);
  }, [anyRunning]);

  const allOn = DEFAULT_PICKS.every((key) => picked.includes(key));
  const selectedBoards = boards.filter((board) => picked.includes(careerPick(board.slug)));
  const boardLine = selectedBoards.length
    ? `${selectedBoards.length} из ${boards.length} · ${selectedBoards
        .slice(0, 3)
        .map((board) => board.name)
        .join(", ")}${selectedBoards.length > 3 ? "…" : ""}`
    : `${boards.length} досок · выключены, пока не отметишь`;
  const sheetTitle = sheetKey ? pickLabel(sheetKey, boards) : "";
  const enabledCount = configs.filter((row) => row.enabled).length;
  const poolPending = crawls.filter((row) => !row.host_subscribed);

  function togglePick(key: string, on: boolean) {
    if (editingId != null && key !== picked[0]) return;
    setPicked((prev) => (on ? [...prev.filter((item) => item !== key), key] : prev.filter((item) => item !== key)));
    if (!on && sheetKey === key) setSheetKey(null);
  }

  function resetForm() {
    setDraft(EMPTY_HUNT_SEARCH);
    setPicked(DEFAULT_PICKS);
    setSheetKey(null);
    setEditingId(null);
    setBoardsOpen(false);
  }

  function goList() {
    resetForm();
    setView("list");
  }

  function alreadyHas(key: string) {
    return configs.some((row) => row.id !== editingId && configCoversPick(row, key, draft, boards));
  }

  const coveredKeys = editingId != null ? [] : picked.filter((key) => alreadyHas(key));
  const missingKeys = picked.filter((key) => !alreadyHas(key));

  async function saveSearch() {
    try {
      const keys = editingId != null ? picked.slice(0, 1) : picked.filter(Boolean);
      if (!keys.length) {
        onError("Включи хотя бы одну площадку");
        return;
      }
      if (editingId != null) {
        const saved = await api.saveConfig(payloadForPick(keys[0], draft, boards), editingId);
        setConfigs((prev) => prev.map((item) => (item.id === saved.id ? saved : item)));
        goList();
        onError(null);
        onStatus("Поиск обновлён");
        await refreshCrawls();
        return;
      }

      const already: string[] = [];
      const savedRows: ScraperConfig[] = [];
      let nextConfigs = configs;
      for (const key of keys) {
        const existing = nextConfigs.find((row) => pickKeyFromConfig(row) === key);
        const payload = payloadForPick(key, draft, boards);
        if (existing && configCoversPick(existing, key, draft, boards)) {
          already.push(key);
          continue;
        }
        const saved = await api.saveConfig(payload, existing?.id);
        savedRows.push(saved);
        nextConfigs = existing
          ? nextConfigs.map((item) => (item.id === saved.id ? saved : item))
          : [...nextConfigs, saved];
      }
      setConfigs(nextConfigs);
      goList();
      onError(null);
      const names = savedRows.map((row) => row.name).join(", ");
      const alreadyNames = already.map((key) => pickLabel(key, boards));
      const bits = [
        savedRows.length ? `Сохранил: ${names}` : "",
        alreadyNames.length ? `без изменений: ${alreadyNames.join(", ")}` : "",
      ].filter(Boolean);
      onStatus(bits.join(". ") || "Без изменений");
      await refreshCrawls();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось сохранить поиск");
    }
  }

  async function subscribeCrawl(row: DonorCrawl) {
    onError(null);
    try {
      const saved = await api.saveConfig({
        name: row.name,
        source: row.source,
        enabled: true,
        interval_minutes: draft.intervalMinutes,
        max_pages: maxPagesForSource(row.source),
        query_params: row.query_params,
      });
      setConfigs((prev) => [...prev, saved]);
      await refreshCrawls();
      onStatus(saved.from_pool ? "Подписался" : "В очереди");
      setView("list");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не подписался");
    }
  }

  function editConfig(config: ScraperConfig) {
    const key = pickKeyFromConfig(config);
    setEditingId(config.id);
    setDraft(draftFromConfig(config));
    setPicked([key]);
    setSheetKey(null);
    setBoardsOpen(key.startsWith("career:"));
    setView("compose");
  }

  async function setEnabled(config: ScraperConfig, on: boolean) {
    onError(null);
    try {
      const saved = await api.saveConfig(
        {
          name: config.name,
          source: config.source,
          enabled: on,
          interval_minutes: config.interval_minutes,
          max_pages: config.max_pages,
          query_params: config.query_params,
          listing_url: config.listing_url ?? undefined,
        },
        config.id,
      );
      setConfigs((prev) => prev.map((item) => (item.id === saved.id ? saved : item)));
      onStatus(on ? "Поиск включён — встанет в очередь" : "Поиск выключен — очередь его больше не берёт");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось выключить поиск");
    }
  }

  async function removeConfig(config: ScraperConfig) {
    onError(null);
    try {
      await api.deleteConfig(config.id);
      setConfigs((prev) => prev.filter((item) => item.id !== config.id));
      if (editingId === config.id) goList();
      onStatus("Поиск удалён. Вакансии в inbox остаются.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось удалить поиск");
    }
  }

  async function run(id: number) {
    setRunningIds((prev) => new Set(prev).add(id));
    onStatus("Идём на сайт заново, кэш этой выдачи не берём.");
    onError(null);
    try {
      await api.runScraper(id);
      void loadStatus();
    } catch (e) {
      setRunningIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      onError(e instanceof Error ? e.message : "Не удалось запустить");
    }
  }

  const saveLabel =
    editingId != null
      ? "Сохранить"
      : missingKeys.length && coveredKeys.length
        ? `Добавить ${missingKeys.length} недостающих`
        : missingKeys.length > 1
          ? "Качать с выбранных"
          : missingKeys.length === 1
            ? `Добавить ${pickLabel(missingKeys[0], boards)}`
            : picked.length
              ? "Уже качает этот поиск"
              : "Качать с выбранных";

  return (
    <div ref={rootRef} className="mx-auto w-full max-w-[560px] pt-4">
      {view === "list" ? (
        <section>
          <div className="flex items-end justify-between gap-4">
            <GuideSpot id="searches.list">
          <div className="flex items-center gap-1.5">
            <h2 className="text-[26px] font-semibold tracking-tight">Поиски</h2>
            <GuideHint id="searches.list" />
            {configs.length > 0 ? <GuideHint id="searches.run" /> : null}
          </div>
              <p className="mt-1 text-[13px] text-muted">
                {enabledCount ? `${enabledCount} активных` : "пока пусто"}
                {anyRunning ? " · очередь качает" : ""}
              </p>
            </GuideSpot>
            <button
              type="button"
              onClick={() => {
                resetForm();
                setView("compose");
              }}
              className="rounded-xl bg-accent/15 px-3 py-2 text-sm text-accent"
            >
              Новый
            </button>
          </div>

          {configs.length === 0 ? (
            <p className="mt-8 text-[14px] leading-6 text-muted">
              Пока пусто. Новый поиск — площадки и фильтры на одном экране, список сюда не вернётся, пока не сохранишь.
            </p>
          ) : (
            <div className="mt-6">
              <GuideSpot id="searches.run">
              {configs.map((c) => {
                const busy =
                  runningIds.has(c.id) || c.last_run?.status === "running" || c.last_run?.status === "queued";
                const line = configRunLine(c, busy);
                return (
                  <div key={c.id} className="border-b border-white/[0.06] py-3.5">
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <SourceBadge source={c.source} label={pickLabel(pickKeyFromConfig(c), boards)} />
                          <p className="truncate font-medium">{c.name}</p>
                        </div>
                        <p
                          className={`mt-1 truncate text-[13px] leading-5 ${
                            line.tone === "err"
                              ? "text-rose-200"
                              : line.tone === "run"
                                ? "text-accent"
                                : "text-muted"
                          }`}
                        >
                          {line.text}
                        </p>
                      </div>
                      <Switch
                        on={c.enabled}
                        onChange={(on) => void setEnabled(c, on)}
                        label={c.enabled ? "Выключить поиск" : "Включить поиск"}
                      />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
                      <button
                        type="button"
                        onClick={() => void run(c.id)}
                        disabled={busy}
                        className="text-accent disabled:opacity-40"
                      >
                        {busy ? (c.last_run?.status === "queued" ? "В очереди" : "Парсит") : "Обновить"}
                      </button>
                      <button type="button" onClick={() => editConfig(c)} className="text-muted hover:text-white">
                        Изменить
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeConfig(c)}
                        className="text-muted hover:text-rose-200"
                      >
                        Удалить
                      </button>
                    </div>
                  </div>
                );
              })}
              </GuideSpot>
            </div>
          )}

          {isHost && crawls.length > 0 && (
            <button
              type="button"
              onClick={() => setView("pool")}
              className="mt-8 text-left text-[14px] text-muted hover:text-white"
            >
              Общий пул · {crawls.length}
              {poolPending.length ? ` · ${poolPending.length} можно взять` : ""}
            </button>
          )}
        </section>
      ) : null}

      {view === "pool" && isHost ? (
        <section>
          <button type="button" onClick={() => setView("list")} className="text-[13px] text-muted hover:text-white">
            ← К поискам
          </button>
          <h2 className="mt-4 text-[26px] font-semibold tracking-tight">Общий пул</h2>
          <div className="mt-6">
            {crawls.map((row) => {
              const waiting = row.queue_status === "pending" || row.queue_status === "running";
              const stale = !row.last_fetched_at;
              return (
                <div key={row.query_key} className="flex items-start gap-3 border-b border-white/[0.06] py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <SourceBadge source={row.source} label={pickLabel(pickKeyFromConfig(row), boards)} />
                      <p className="truncate font-medium">{row.name}</p>
                    </div>
                    <p className="mt-1 text-[13px] leading-5 text-muted">
                      {waiting
                        ? row.queue_status === "running"
                          ? "парсит"
                          : "в очереди"
                        : stale
                          ? "ещё не качали"
                          : row.last_status === "error"
                            ? row.last_error || "ошибка прогона"
                            : `кэш ${relativeTime(row.last_fetched_at) || "только что"} · ${row.found_count}`}
                    </p>
                  </div>
                  {row.host_subscribed ? (
                    <span className="shrink-0 px-1 py-2 text-sm text-muted">своё</span>
                  ) : (
                    <button
                      type="button"
                      className="shrink-0 text-sm text-accent"
                      onClick={() => void subscribeCrawl(row)}
                    >
                      В inbox
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {view === "compose" ? (
        <section className="pb-8">
          <button type="button" onClick={goList} className="text-[13px] text-muted hover:text-white">
            ← К поискам
          </button>
          <h2 className="mt-4 text-[26px] font-semibold tracking-tight">
            {editingId != null ? "Изменить поиск" : "Новый поиск"}
          </h2>
          <p className="mt-2 text-[13px] leading-5 text-muted">
            {editingId != null && picked[0]
              ? pickLabel(picked[0], boards)
              : `${picked.length || 0} площадок · все встанут в очередь`}
          </p>

          <div className="mt-8">
            <GuideSpot id="searches.platforms">
            <div className="mb-2 flex items-center gap-1.5">
              <p className="text-[12px] tracking-[0.12em] text-muted uppercase">Площадки</p>
              <GuideHint id="searches.platforms" />
            </div>
            {editingId == null && (
              <div className="flex items-center justify-between gap-4 border-b border-white/[0.08] py-3">
                <p className="text-[15px] font-medium">Все агрегаторы</p>
                <Switch
                  on={allOn}
                  onChange={(on) => {
                    setPicked((prev) => {
                      const company = prev.filter((item) => item.startsWith("career:"));
                      return on ? [...DEFAULT_PICKS, ...company] : company;
                    });
                    if (!on) setSheetKey(null);
                  }}
                  label="Все агрегаторы"
                />
              </div>
            )}
            {AGGREGATORS.map((item) => {
              const covered = editingId == null && alreadyHas(item.value);
              return (
                <SourceSwitchRow
                  key={item.value}
                  name={item.label}
                  hint={covered ? "уже качает этот поиск" : item.hint}
                  color={item.color}
                  on={picked.includes(item.value)}
                  disabled={editingId != null && picked[0] !== item.value}
                  onChange={(on) => togglePick(item.value, on)}
                  onOpen={() => setSheetKey(item.value)}
                />
              );
            })}
            {editingId == null ? (
              <div className="flex items-center justify-between gap-4 border-b border-white/[0.08] py-3">
                <button type="button" onClick={() => setBoardsOpen((open) => !open)} className="min-w-0 text-left">
                  <p className="text-[15px] font-medium">Сайты компаний</p>
                  <p className="mt-0.5 text-[13px] text-muted">
                    {boardLine}
                    {boardsOpen ? " · свернуть" : ""}
                  </p>
                </button>
                <Switch
                  on={boards.length > 0 && boards.every((board) => picked.includes(careerPick(board.slug)))}
                  onChange={(on) => {
                    const boardKeys = boards.map((board) => careerPick(board.slug));
                    setPicked((prev) => {
                      const rest = prev.filter((item) => !item.startsWith("career:"));
                      return on ? [...rest, ...boardKeys] : rest;
                    });
                    if (on) setBoardsOpen(true);
                  }}
                  label="Все сайты компаний"
                />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setBoardsOpen((open) => !open)}
                className="flex w-full items-center justify-between border-b border-white/[0.08] py-3.5 text-left"
              >
                <span className="text-[15px] font-medium">Сайты компаний</span>
                <span className="text-[13px] text-muted">
                  {boardLine}
                  {boardsOpen ? " · свернуть" : ""}
                </span>
              </button>
            )}
            {boardsOpen ? (
              <BoardPickList
                boards={boards}
                picked={picked}
                editingId={editingId}
                alreadyHas={alreadyHas}
                onToggle={togglePick}
              />
            ) : null}
            </GuideSpot>
          </div>

          <div className="mt-10 space-y-5">
            <label className="block space-y-2">
              <GuideLabel id="searches.query" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Что ищем
              </GuideLabel>
              <input
                value={draft.search}
                onChange={(e) => setDraft((prev) => ({ ...prev, search: e.target.value }))}
                placeholder="Python, QA, Go…"
              />
            </label>
            <fieldset className="space-y-2">
              <GuideLabel id="searches.format" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Формат
              </GuideLabel>
              <FilterChips
                variant="pill"
                options={SEARCH_FORMATS}
                value={draft.formats}
                onChange={(formats) => setDraft((prev) => ({ ...prev, formats }))}
              />
            </fieldset>
            <fieldset className="space-y-2">
              <GuideLabel id="searches.grade" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Грейд
              </GuideLabel>
              <FilterChips
                variant="pill"
                options={SEARCH_LEVELS}
                value={draft.levels}
                onChange={(levels) => setDraft((prev) => ({ ...prev, levels }))}
              />
            </fieldset>
            <fieldset className="space-y-2">
              <GuideLabel id="searches.stack" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Стек
              </GuideLabel>
              {SEARCH_STACK_GROUPS.map((group) => (
                <div key={group.label} className="space-y-2">
                  <p className="text-[13px] text-muted">{group.label}</p>
                  <FilterChips
                    variant="pill"
                    options={[...group.items]}
                    value={draft.stack}
                    onChange={(stack) => setDraft((prev) => ({ ...prev, stack }))}
                  />
                </div>
              ))}
            </fieldset>
            <fieldset className="space-y-2">
              <GuideLabel id="searches.city" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Где
              </GuideLabel>
              <CityPicker
                variant="pill"
                value={draft.cities}
                onChange={(cities) => setDraft((prev) => ({ ...prev, cities }))}
              />
            </fieldset>
            <GuideSpot id="searches.paid" className="flex items-center justify-between gap-4 border-b border-white/[0.08] py-3">
              <span className="inline-flex items-center gap-1.5">
                <p className="text-[15px] font-medium">Только с зарплатой</p>
                <GuideHint id="searches.paid" />
              </span>
              <Switch
                on={draft.onlySalary}
                onChange={(onlySalary) => setDraft((prev) => ({ ...prev, onlySalary }))}
                label="Только с зарплатой"
              />
            </GuideSpot>
            <fieldset className="space-y-2">
              <GuideLabel id="searches.salary" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Зарплата от
              </GuideLabel>
              <ChoiceChips
                variant="pill"
                options={SEARCH_SALARIES.map((item) => ({ value: String(item.value), label: item.label }))}
                value={SEARCH_SALARIES.some((item) => item.value === draft.salaryFrom) ? String(draft.salaryFrom) : ""}
                onChange={(value) => setDraft((prev) => ({ ...prev, salaryFrom: Number(value) || 0 }))}
              />
              <input
                type="number"
                min={0}
                step={10000}
                inputMode="numeric"
                placeholder="своя сумма, ₽"
                value={draft.salaryFrom ? String(draft.salaryFrom) : ""}
                onChange={(e) => {
                  const raw = e.target.value.replace(/\D/g, "");
                  setDraft((prev) => ({ ...prev, salaryFrom: raw ? Number(raw) : 0 }));
                }}
              />
            </fieldset>
            <label className="space-y-2">
              <GuideLabel id="searches.interval" className="text-[12px] tracking-[0.12em] text-muted uppercase">
                Как часто
              </GuideLabel>
              <select
                value={draft.intervalMinutes}
                onChange={(e) => setDraft((prev) => ({ ...prev, intervalMinutes: Number(e.target.value) }))}
              >
                <option value={30}>каждые 30 мин</option>
                <option value={60}>каждый час</option>
                <option value={180}>каждые 3 часа</option>
                <option value={360}>каждые 6 часов</option>
              </select>
            </label>
          </div>

          <div className="sticky bottom-0 z-10 mt-8 border-t border-white/[0.06] bg-bg py-4">
            <button
              onClick={() => void saveSearch()}
              disabled={!picked.length}
              className="w-full rounded-xl border border-accent/40 bg-accent/15 px-4 py-2.5 text-[14px] text-accent disabled:opacity-40"
            >
              {saveLabel}
            </button>
          </div>
        </section>
      ) : null}

      {sheetKey ? (
        <SearchSourceSheet
          pickKey={sheetKey}
          title={sheetTitle}
          draft={draft}
          boards={boards}
          onChange={setDraft}
          onClose={() => setSheetKey(null)}
        />
      ) : null}
    </div>
  );
}
