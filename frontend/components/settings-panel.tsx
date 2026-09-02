"use client";

import { useEffect, useState } from "react";
import { api, type AuthUser } from "@/lib/api";
import type { CustomFieldDef, Profile, ScraperConfig } from "@/lib/types";
import { ChoiceChips, FilterChips, ToggleChip } from "@/components/filter-chips";
import { SourceBadge, sourceLabel } from "@/components/source-badge";
import { TelegramPoolPanel } from "@/components/telegram-pool";
import { GoogleCalendarPanel } from "@/components/google-calendar-panel";
import { HuntFieldsEditor } from "@/components/hunt-fields-editor";
import { useHunt } from "@/components/hunt-context";
import { useWorkspace } from "@/components/workspace-context";
import { fromNow, relativeTime } from "@/lib/format";
import {
  CATEGORIES,
  CONTACTS,
  EMPTY_FILTERS,
  ENGLISH,
  FORMATS,
  LEVELS,
  SORTS,
  SUBCATEGORIES,
  autoName,
  filtersFromParams,
  summarize,
  type HireHiFilters,
} from "@/lib/hirehi-filters";
import {
  EMPTY_HH_FILTERS,
  HH_AREAS,
  HH_EMPLOYMENT,
  HH_EXPERIENCE,
  HH_PERIODS,
  HH_SCHEDULE,
  HH_SORTS,
  hhAutoName,
  hhFiltersFromParams,
  hhSummarize,
  type HhFilters,
} from "@/lib/hh-filters";

type Source = "hirehi" | "hh";

const SOURCES: { value: Source; label: string }[] = [
  { value: "hirehi", label: "HireHi" },
  { value: "hh", label: "hh.ru" },
];

function configSource(config: ScraperConfig): Source {
  return config.source === "hh" ? "hh" : "hirehi";
}

function configSummary(config: ScraperConfig): string {
  return configSource(config) === "hh"
    ? hhSummarize(hhFiltersFromParams(config.query_params))
    : summarize(filtersFromParams(config.query_params));
}

function configRunLine(config: ScraperConfig, runningNow: boolean): { text: string; tone: "ok" | "err" | "run" | "idle" } {
  if (runningNow || config.last_run?.status === "running") {
    return {
      text: config.source === "hh" ? "ищет вакансии… hh.ru может занять 2–5 мин" : "ищет вакансии…",
      tone: "run",
    };
  }
  if (!config.enabled) {
    return { text: "выключен — сам не ходит, можно запустить вручную", tone: "idle" };
  }
  const last = config.last_run;
  if (!last) {
    return { text: "ещё не запускался — нажми «Запустить»", tone: "idle" };
  }
  if (last.status === "error") {
    return { text: last.error || "ошибка последнего прогона", tone: "err" };
  }
  const when = relativeTime(last.finished_at || last.started_at) || "только что";
  const next = config.next_run_at ? ` · следующий ${fromNow(config.next_run_at)}` : "";
  return {
    text: `${when} · найдено ${last.found_count} · новых ${last.new_count}${next}`,
    tone: "ok",
  };
}

export function SettingsPanel() {
  const { hunts, activeHuntId, refresh: refreshHunts } = useHunt();
  const { me, users, asUserId, refreshUsers } = useWorkspace();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [configs, setConfigs] = useState<ScraperConfig[]>([]);
  const [resume, setResume] = useState("");
  const [source, setSource] = useState<Source>("hirehi");
  const [filters, setFilters] = useState<HireHiFilters>(EMPTY_FILTERS);
  const [hhFilters, setHhFilters] = useState<HhFilters>(EMPTY_HH_FILTERS);
  const [intervalMinutes, setIntervalMinutes] = useState(60);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [runningIds, setRunningIds] = useState<Set<number>>(new Set());
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"profile" | "fields" | "calendar" | "telegram" | "searches" | "people">("profile");
  const [fields, setFields] = useState<CustomFieldDef[]>([]);
  const [fieldsHuntId, setFieldsHuntId] = useState<number | null>(null);

  async function load() {
    const [p, c, me] = await Promise.all([api.profile(), api.configs(), api.me()]);
    setProfile(p);
    setResume(p.resume_text ?? "");
    setFields(p.custom_fields || []);
    setConfigs(c);
    setUser(me);
  }

  useEffect(() => {
    if (!fieldsHuntId) {
      const next = activeHuntId ?? hunts[0]?.id ?? null;
      if (next) setFieldsHuntId(next);
      return;
    }
    const hunt = hunts.find((item) => item.id === fieldsHuntId);
    if (hunt) setFields(hunt.custom_fields || []);
  }, [hunts, fieldsHuntId, activeHuntId]);

  async function loadStatus() {
    const [c] = await Promise.all([api.configs()]);
    setConfigs(c);
    setRunningIds((prev) => {
      const next = new Set(prev);
      for (const config of c) {
        if (config.last_run && config.last_run.status !== "running") next.delete(config.id);
      }
      return next;
    });
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [asUserId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") && me?.is_host) setTab("calendar");
    if (params.get("tab") === "fields") setTab("fields");
  }, [me]);

  useEffect(() => {
    if (!me?.is_host && (tab === "calendar" || tab === "telegram" || tab === "people")) {
      setTab("profile");
    }
  }, [me, tab]);

  const anyRunning =
    runningIds.size > 0 || configs.some((c) => c.last_run?.status === "running");

  useEffect(() => {
    const ms = anyRunning ? 2000 : 15000;
    const timer = window.setInterval(() => {
      void loadStatus();
    }, ms);
    return () => window.clearInterval(timer);
  }, [anyRunning]);

  function patchFilters(partial: Partial<HireHiFilters>) {
    setFilters((prev) => ({ ...prev, ...partial }));
  }

  function patchHh(partial: Partial<HhFilters>) {
    setHhFilters((prev) => ({ ...prev, ...partial }));
  }

  function resetForm() {
    setFilters(EMPTY_FILTERS);
    setHhFilters(EMPTY_HH_FILTERS);
    setIntervalMinutes(source === "hh" ? 180 : 60);
    setEditingId(null);
  }

  function switchSource(next: Source) {
    if (next === source) return;
    setSource(next);
    setFilters(EMPTY_FILTERS);
    setHhFilters(EMPTY_HH_FILTERS);
    setIntervalMinutes(next === "hh" ? 180 : 60);
    setEditingId(null);
  }

  async function saveProfile() {
    setError(null);
    try {
      const p = await api.saveProfile({
        resume_text: resume,
      });
      setProfile(p);
      setStatus("Профиль сохранён");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  async function saveFields() {
    setError(null);
    try {
      if (fieldsHuntId) {
        const saved = await api.saveHuntFields(fieldsHuntId, fields);
        setFields(saved.custom_fields || fields);
        await refreshHunts();
      } else {
        const p = await api.saveProfile({ custom_fields: fields });
        setProfile(p);
        setFields(p.custom_fields || []);
      }
      setStatus("Поля сохранены");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  async function onFile(file: File) {
    const p = await api.uploadResume(file);
    setProfile(p);
    setResume(p.resume_text ?? "");
    setStatus(`Резюме из файла: ${p.resume_filename}`);
  }

  async function saveSearch() {
    try {
      const payload =
        source === "hh"
          ? {
              name: hhAutoName(hhFilters),
              source: "hh" as const,
              enabled: true,
              interval_minutes: intervalMinutes,
              max_pages: 3,
              query_params: hhFilters,
            }
          : {
              name: autoName(filters),
              source: "hirehi" as const,
              enabled: true,
              interval_minutes: intervalMinutes,
              max_pages: 5,
              query_params: filters,
            };
      const saved = await api.saveConfig(payload, editingId ?? undefined);
      setConfigs((prev) =>
        editingId ? prev.map((item) => (item.id === saved.id ? saved : item)) : [...prev, saved],
      );
      resetForm();
      setError(null);
      setStatus(editingId ? "Поиск обновлён" : "Поиск добавлен");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить поиск");
    }
  }

  function editConfig(config: ScraperConfig) {
    const next = configSource(config);
    setSource(next);
    setIntervalMinutes(config.interval_minutes);
    setEditingId(config.id);
    if (next === "hh") {
      setHhFilters(hhFiltersFromParams(config.query_params));
      setFilters(EMPTY_FILTERS);
    } else {
      setFilters(filtersFromParams(config.query_params));
      setHhFilters(EMPTY_HH_FILTERS);
    }
  }

  async function run(id: number) {
    setRunningIds((prev) => new Set(prev).add(id));
    setStatus("Парсер пошёл. Статус на карточке обновится сам.");
    setError(null);
    try {
      await api.runScraper(id);
      void loadStatus();
    } catch (e) {
      setRunningIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      setError(e instanceof Error ? e.message : "Не удалось запустить");
    }
  }

  const previewName = source === "hh" ? hhAutoName(hhFilters) : autoName(filters);
  const TABS = [
    { id: "profile" as const, label: "Профиль" },
    { id: "fields" as const, label: "Поля охоты" },
    { id: "searches" as const, label: "Поиски" },
    ...(me?.is_host
      ? [
          { id: "calendar" as const, label: "Календарь" },
          { id: "telegram" as const, label: "Telegram" },
          { id: "people" as const, label: "Люди" },
        ]
      : []),
  ];

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 items-center px-7 pt-6 pb-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Настройки</h1>
          <p className="mt-0.5 text-[12px] text-muted">
            {me?.is_host ? "резюме, поля, календарь, поиски и кто видит чужие данные" : "резюме, поля карточек и поиски"}
          </p>
        </div>
      </header>
      {error && <p className="mx-7 mb-3 text-sm text-rose-200">{error}</p>}
      {status && <p className="px-7 pb-2 text-[13px] text-accent">{status}</p>}

      <div className="flex min-h-0 flex-1 border-t border-line">
        <aside className="w-[200px] shrink-0 overflow-y-auto border-r border-line py-2">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`flex w-full px-5 py-2.5 text-left text-[14px] ${
                tab === item.id ? "bg-white/[0.05] text-white" : "text-muted hover:bg-white/[0.03] hover:text-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </aside>
        <div className="min-w-0 flex-1 overflow-y-auto px-10 py-6">
      {tab === "profile" && (
      <div className="mx-auto w-full max-w-[480px] space-y-10 pt-4">
      <section className="space-y-4">
        <h2 className="text-[26px] font-semibold tracking-tight">Профиль</h2>
        <p className="text-[13px] text-muted">Твоё базовое резюме: вставь текст или загрузи файл.</p>
        <textarea className="field-area" rows={12} value={resume} onChange={(e) => setResume(e.target.value)} placeholder="Вставь текст резюме…" />
        <div className="flex items-center gap-3">
          <label className="rounded-xl bg-white/6 px-3 py-2 text-sm">
            Загрузить PDF / TXT
            <input
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void onFile(file);
              }}
            />
          </label>
          {profile?.resume_filename && <span className="text-sm text-muted">{profile.resume_filename}</span>}
        </div>
        <button onClick={() => void saveProfile()} className="text-[14px] text-accent">
          Сохранить профиль
        </button>
      </section>
      {!me?.is_host && (
        <section className="space-y-3">
          <h2 className="text-[26px] font-semibold tracking-tight">Общий пул</h2>
          <p className="text-[13px] leading-5 text-muted">
            Вакансии из общих каналов копируются в твой inbox. Воронка и контакты остаются свои.
          </p>
          <button
            type="button"
            className="text-[14px] text-accent"
            onClick={async () => {
              try {
                const result = await api.joinTelegramPool();
                setError(null);
                setStatus(result.new_count ? `В inbox ${result.new_count}` : "Уже в пуле");
              } catch (e) {
                setError(e instanceof Error ? e.message : "Не подключилось");
              }
            }}
          >
            Подключить
          </button>
        </section>
      )}
      </div>
      )}

      {tab === "fields" && (
        <HuntFieldsEditor
          fields={fields}
          onChange={setFields}
          onSave={() => void saveFields()}
          huntName={hunts.find((item) => item.id === fieldsHuntId)?.name}
          hunts={hunts}
          huntId={fieldsHuntId}
          onHuntId={setFieldsHuntId}
        />
      )}

      {tab === "calendar" && me?.is_host && <GoogleCalendarPanel />}
      {tab === "telegram" && me?.is_host && <TelegramPoolPanel user={me} />}

      {tab === "people" && me?.is_host && (
        <div className="mx-auto w-full max-w-[480px] space-y-6 pt-4">
          <div>
            <h2 className="text-[26px] font-semibold tracking-tight">Люди</h2>
            <p className="mt-2 text-[13px] leading-5 text-muted">
              У каждого свой inbox, воронка, время и контакты. Кому можно смотреть чужие аккаунты — включи ниже. Общий пул контактов всех видишь только ты.
            </p>
          </div>
          {users.filter((row) => row.id !== me.id).length === 0 && (
            <p className="text-[14px] text-muted">Пока никто кроме тебя не зарегистрировался.</p>
          )}
          {users
            .filter((row) => row.id !== me.id)
            .map((row) => (
              <div key={row.id} className="flex items-center justify-between gap-4 border-b border-white/[0.06] py-3">
                <div className="min-w-0">
                  <p className="truncate text-[15px]">{row.email}</p>
                  <p className="mt-0.5 text-[13px] text-muted">
                    {row.can_observe ? "видит чужие аккаунты" : "только своё"}
                  </p>
                </div>
                <button
                  type="button"
                  className="shrink-0 text-[14px] text-accent"
                  onClick={async () => {
                    try {
                      await api.setObserve(row.id, !row.can_observe);
                      await refreshUsers();
                      setStatus(row.can_observe ? "Снял доступ" : "Может смотреть всех");
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Не сохранилось");
                    }
                  }}
                >
                  {row.can_observe ? "Забрать" : "Разрешить смотреть"}
                </button>
              </div>
            ))}
        </div>
      )}

      {tab === "searches" && (
      <div className="mx-auto w-full max-w-[560px] space-y-10 pt-4">
      <section className="space-y-5">
        <div>
          <h2 className="text-[26px] font-semibold tracking-tight">Поиски</h2>
          <p className="mt-2 text-[13px] leading-5 text-muted">
            Hunt сам подтягивает вакансии по расписанию. Чтобы проверить сейчас — нажми «Запустить». На hh.ru первый прогон может занять несколько минут.
          </p>
        </div>

        {configs.map((c) => {
          const busy = runningIds.has(c.id) || c.last_run?.status === "running";
          const line = configRunLine(c, busy);
          return (
            <div key={c.id} className="flex items-start gap-3 border-b border-white/[0.06] py-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <SourceBadge source={c.source} />
                  <p className="truncate font-medium">{c.name}</p>
                </div>
                <p className="mt-0.5 text-[13px] text-muted">{configSummary(c)}</p>
                <p
                  className={`mt-1 text-[13px] leading-5 ${
                    line.tone === "err"
                      ? "text-rose-200"
                      : line.tone === "run"
                        ? "text-accent"
                        : "text-muted"
                  }`}
                >
                  {line.text}
                </p>
                <p className="text-[12px] text-muted">
                  {c.enabled ? `расписание: каждые ${c.interval_minutes} мин` : "расписание выключено"}
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-stretch gap-1">
                <button
                  onClick={() => void run(c.id)}
                  disabled={busy}
                  className="rounded-xl bg-accent/15 px-3 py-2 text-sm text-accent disabled:opacity-50"
                >
                  {busy ? "Парсит…" : "Запустить"}
                </button>
                <button onClick={() => editConfig(c)} className="rounded-xl px-3 py-2 text-sm text-muted hover:text-white">
                  Изменить
                </button>
                <button
                  onClick={async () => {
                    await api.deleteConfig(c.id);
                    setConfigs((prev) => prev.filter((x) => x.id !== c.id));
                    if (editingId === c.id) resetForm();
                  }}
                  className="rounded-xl px-3 py-2 text-sm text-muted hover:text-rose-200"
                >
                  Удалить
                </button>
              </div>
            </div>
          );
        })}

        <div className="space-y-6">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-[13px] text-muted">{editingId ? "Редактирование поиска" : "Новый поиск"}</p>
              <p className="mt-1 text-[15px] font-medium">{previewName}</p>
            </div>
            {editingId != null && (
              <button type="button" onClick={resetForm} className="text-sm text-muted hover:text-white">
                Отмена
              </button>
            )}
          </div>

          <fieldset className="space-y-2">
            <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Источник</legend>
            <ChoiceChips options={SOURCES} value={source} onChange={(next) => switchSource(next as Source)} />
          </fieldset>

          {source === "hh" ? (
            <>
              <p className="rounded-xl bg-white/4 px-3 py-2 text-[13px] leading-5 text-muted">
                hh.ru не отдаёт вакансии через API, поэтому Hunt открывает Chrome. Если появится капча — включи «показать Chrome» и пройди проверку в окне.
              </p>
              <label className="block space-y-2">
                <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Что ищем</span>
                <input
                  value={hhFilters.search}
                  onChange={(e) => patchHh({ search: e.target.value })}
                  placeholder="QA lead, Python, product manager…"
                />
              </label>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Где</legend>
                <FilterChips
                  options={HH_AREAS}
                  value={hhFilters.area}
                  onChange={(area) => patchHh({ area: area.length ? area : ["1"] })}
                />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Опыт</legend>
                <FilterChips
                  options={HH_EXPERIENCE}
                  value={hhFilters.experience}
                  onChange={(experience) => patchHh({ experience })}
                />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">График</legend>
                <FilterChips
                  options={HH_SCHEDULE}
                  value={hhFilters.schedule}
                  onChange={(schedule) => patchHh({ schedule })}
                />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Занятость</legend>
                <FilterChips
                  options={HH_EMPLOYMENT}
                  value={hhFilters.employment}
                  onChange={(employment) => patchHh({ employment })}
                />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Ещё</legend>
                <div className="flex flex-wrap gap-2">
                  <ToggleChip
                    label="только с зарплатой"
                    on={hhFilters.only_with_salary}
                    onChange={(only_with_salary) => patchHh({ only_with_salary })}
                  />
                  <ToggleChip
                    label="показать Chrome"
                    on={hhFilters.headed}
                    onChange={(headed) => patchHh({ headed })}
                  />
                </div>
              </fieldset>
              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-2">
                  <span className="block text-[12px] tracking-[0.12em] text-muted uppercase">Сортировка</span>
                  <select value={hhFilters.order_by} onChange={(e) => patchHh({ order_by: e.target.value })}>
                    {HH_SORTS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-2">
                  <span className="block text-[12px] tracking-[0.12em] text-muted uppercase">Период</span>
                  <select
                    value={hhFilters.search_period}
                    onChange={(e) => patchHh({ search_period: e.target.value })}
                  >
                    {HH_PERIODS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </>
          ) : (
            <>
              <label className="block space-y-2">
                <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Что ищем</span>
                <input
                  value={filters.search}
                  onChange={(e) => patchFilters({ search: e.target.value })}
                  placeholder="Java, ML, backend…"
                />
              </label>
              <label className="block space-y-2">
                <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Категория</span>
                <select value={filters.category} onChange={(e) => patchFilters({ category: e.target.value })}>
                  {CATEGORIES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Стек</legend>
                <FilterChips
                  options={SUBCATEGORIES}
                  value={filters.subcategory}
                  onChange={(subcategory) => patchFilters({ subcategory })}
                />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Формат</legend>
                <FilterChips options={FORMATS} value={filters.format} onChange={(format) => patchFilters({ format })} />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Грейд</legend>
                <FilterChips options={LEVELS} value={filters.level} onChange={(level) => patchFilters({ level })} />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Ещё</legend>
                <FilterChips options={ENGLISH} value={filters.english} onChange={(english) => patchFilters({ english })} />
                <FilterChips
                  options={CONTACTS}
                  value={filters.direct_contact}
                  onChange={(direct_contact) => patchFilters({ direct_contact })}
                />
              </fieldset>
              <label className="space-y-2">
                <span className="block text-[12px] tracking-[0.12em] text-muted uppercase">Сортировка</span>
                <select value={filters.sort} onChange={(e) => patchFilters({ sort: e.target.value })}>
                  {SORTS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

          <label className="space-y-2">
            <span className="block text-[12px] tracking-[0.12em] text-muted uppercase">Как часто</span>
            <select value={intervalMinutes} onChange={(e) => setIntervalMinutes(Number(e.target.value))}>
              <option value={15}>каждые 15 мин</option>
              <option value={30}>каждые 30 мин</option>
              <option value={60}>каждый час</option>
              <option value={180}>каждые 3 часа</option>
              <option value={360}>каждые 6 часов</option>
            </select>
          </label>

          <button onClick={() => void saveSearch()} className="text-[14px] text-accent">
            {editingId ? "Сохранить изменения" : `Добавить поиск ${sourceLabel(source)}`}
          </button>
        </div>
      </section>
      </div>
      )}
        </div>
      </div>
    </div>
  );
}
