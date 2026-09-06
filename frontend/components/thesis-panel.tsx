"use client";

import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import type { NudgeOut, Thesis } from "@/lib/types";
import { FilterChips, ToggleChip } from "@/components/filter-chips";
import { GuideHint, GuideLabel, GuideSpot } from "@/components/guide";
import { CompanyExcludeInput } from "@/components/company-exclude-input";
import { FORMATS, LEVELS } from "@/lib/hirehi-filters";
import { WaveDesk } from "@/components/wave-desk";
import { NudgeQueue } from "@/components/nudge-queue";
import { VacancyDrawer } from "@/components/vacancy-drawer";
import { SalaryCorridorBlock } from "@/components/salary-corridor";
import { relativeTime } from "@/lib/format";
import { PageHead } from "./page-head";
import { marketDot, marketLabel, marketTone } from "@/lib/hunt-copy";

const EMPTY: Omit<Thesis, "id" | "last_verdict" | "last_reason" | "last_evaluated_at" | "stats" | "enabled"> = {
  name: "",
  role_query: "",
  grades: [],
  formats: [],
  salary_min: null,
  no_nda: false,
  exclude_companies: [],
  days: 14,
  min_sample: 8,
  min_median_match: 55,
};

function verdictTone(verdict: string | null | undefined) {
  return marketTone(verdict);
}

function verdictDot(verdict: string | null | undefined) {
  return marketDot(verdict);
}

function verdictLabel(verdict: string | null | undefined) {
  return marketLabel(verdict);
}

export function ThesisPanel() {
  const { activeHuntId, setActiveHuntId, refresh: refreshHunts } = useHunt();
  const [items, setItems] = useState<Thesis[]>([]);
  const [nudge, setNudge] = useState<NudgeOut | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [composer, setComposer] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [waveId, setWaveId] = useState<number | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(false);

  async function load() {
    const [data, ping] = await Promise.all([api.theses(), api.nudge()]);
    setItems(data);
    setNudge(ping);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, []);

  useEffect(() => {
    const write = new URLSearchParams(window.location.search).get("write");
    if (write && activeHuntId) setWaveId(activeHuntId);
  }, [activeHuntId]);

  const selected = items.find((item) => item.id === selectedId) ?? items[0] ?? null;

  useEffect(() => {
    if (activeHuntId && items.some((item) => item.id === activeHuntId)) {
      setSelectedId(activeHuntId);
      return;
    }
    if (selectedId && items.some((item) => item.id === selectedId)) return;
    setSelectedId(items[0]?.id ?? null);
  }, [items, selectedId, activeHuntId]);

  function patch<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY);
    setComposer(true);
    setWaveId(null);
    setError(null);
  }

  function startEdit(thesis: Thesis) {
    setEditingId(thesis.id);
    setForm({
      name: thesis.name,
      role_query: thesis.role_query,
      grades: thesis.grades || [],
      formats: thesis.formats || [],
      salary_min: thesis.salary_min,
      no_nda: thesis.no_nda,
      exclude_companies: thesis.exclude_companies || [],
      days: thesis.days,
      min_sample: thesis.min_sample,
      min_median_match: thesis.min_median_match,
    });
    setComposer(true);
    setWaveId(null);
  }

  async function save() {
    setError(null);
    try {
      const saved = await api.saveThesis(
        { ...form, enabled: true, name: form.name.trim() || "Направление" },
        editingId ?? undefined,
      );
      setStatus(editingId ? "Сохранил направление" : "Направление добавлено");
      setEditingId(null);
      setForm(EMPTY);
      setComposer(false);
      setSelectedId(saved.id);
      await load();
      await refreshHunts();
      await setActiveHuntId(saved.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сохранилось");
    }
  }

  const waveThesis = items.find((item) => item.id === waveId) ?? null;
  const pingCount = selected
    ? (nudge?.groups.find((g) => g.thesis_id === selected.id)?.items.length ?? 0)
    : 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex shrink-0 items-end gap-6 px-7 pt-5 pb-4">
        <GuideSpot id="thesis.header" className="min-w-0 flex-1">
          <PageHead
            title="направления"
            count={items.length ? `${items.length} · какие вакансии смотришь` : "какие вакансии смотришь"}
            hint={<GuideHint id="thesis.header" />}
          />
        </GuideSpot>
        <button
          type="button"
          onClick={() => {
            if (composer) {
              setComposer(false);
              setEditingId(null);
              setForm(EMPTY);
            } else startCreate();
          }}
          className={`chip ml-auto${composer ? " chip-on" : ""}`}
        >
          {composer ? <X size={14} /> : <Plus size={14} />}
          {composer ? "Закрыть" : "направление"}
        </button>
      </header>

      {error && (
        <p className="mx-7 mb-3 rounded-xl border border-rose-400/20 bg-rose-400/8 px-4 py-2.5 text-sm text-rose-100">
          {error}
        </p>
      )}
      {status && !error && <p className="px-7 pb-2 text-[13px] text-accent">{status}</p>}

      {nudge && nudge.total > 0 && !composer && (
        <NudgeQueue
          afterDays={nudge.after_days}
          groups={nudge.groups}
          calendarConnected={nudge.calendar_connected}
          onOpen={setOpenId}
          onChanged={() => void load()}
        />
      )}

      <div className="flex min-h-0 flex-1 border-t border-line">
        <GuideSpot id="thesis.list" className="w-[280px] shrink-0 overflow-y-auto border-r border-line py-2">
          <div className="flex justify-end px-3 pb-1">
            <GuideHint id="thesis.list" />
          </div>
          {items.length === 0 ? (
            <p className="px-5 py-6 text-[13px] text-muted">Пока нет направлений</p>
          ) : (
            items.map((thesis) => {
              const active = selected?.id === thesis.id && !composer && !waveThesis;
              const verdict = thesis.stats?.verdict ?? thesis.last_verdict;
              return (
                <button
                  key={thesis.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(thesis.id);
                    setComposer(false);
                    setWaveId(null);
                    void setActiveHuntId(thesis.id);
                  }}
                  data-active={active ? "true" : undefined}
                  className="row flex w-full items-start gap-3 px-4 py-3 text-left"
                >
                  <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${verdictDot(verdict)}`} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] leading-5">{thesis.name}</span>
                    <span className={`mt-0.5 block text-[12px] ${verdictTone(verdict)}`}>
                      {verdictLabel(verdict)}
                    </span>
                  </span>
                </button>
              );
            })
          )}
        </GuideSpot>

        <section className="min-w-0 flex-1 overflow-y-auto px-10 py-6">
          {composer ? (
            <form
              className="mx-auto w-full max-w-[480px] pt-4"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <h2 className="text-[26px] font-semibold tracking-tight">
                {editingId ? "Изменить направление" : "Новое направление"}
              </h2>
              <p className="mt-2 text-[13px] leading-5 text-muted">
                Например «Python senior удалёнка». Inbox и воронка покажут только эти вакансии. В шапке можно переключаться между направлениями.
              </p>
              <div className="mt-8 space-y-6">
                <label className="block">
                  <GuideLabel id="thesis.name" className="mb-2 text-[12px] text-muted">
                    Название
                  </GuideLabel>
                  <input
                    className="field-line"
                    value={form.name}
                    onChange={(e) => patch("name", e.target.value)}
                    placeholder="Python senior remote"
                    autoFocus
                  />
                </label>
                <label className="block">
                  <GuideLabel id="thesis.query" className="mb-2 text-[12px] text-muted">
                    Запрос
                  </GuideLabel>
                  <input
                    className="field-line"
                    value={form.role_query}
                    onChange={(e) => patch("role_query", e.target.value)}
                    placeholder="python, senior — слова из роли или компании"
                  />
                </label>
                <fieldset>
                  <GuideLabel id="thesis.grades" className="mb-2 text-[12px] text-muted">
                    Грейд
                  </GuideLabel>
                  <FilterChips options={LEVELS} value={form.grades} onChange={(grades) => patch("grades", grades)} />
                </fieldset>
                <fieldset>
                  <GuideLabel id="thesis.formats" className="mb-2 text-[12px] text-muted">
                    Формат
                  </GuideLabel>
                  <FilterChips options={FORMATS} value={form.formats} onChange={(formats) => patch("formats", formats)} />
                </fieldset>
                <label>
                  <GuideLabel id="thesis.salary" className="mb-2 text-[12px] text-muted">
                    Мин. зп
                  </GuideLabel>
                  <input
                    className="field-line"
                    type="number"
                    value={form.salary_min ?? ""}
                    onChange={(e) => patch("salary_min", e.target.value ? Number(e.target.value) : null)}
                    placeholder="350000"
                  />
                </label>
                <ToggleChip label="без NDA" on={form.no_nda} onChange={(no_nda) => patch("no_nda", no_nda)} />
                <label className="block">
                  <GuideLabel id="thesis.exclude" className="mb-2 text-[12px] text-muted">
                    Кроме компаний
                  </GuideLabel>
                  <div className="field-line">
                    <CompanyExcludeInput
                      value={form.exclude_companies}
                      onChange={(exclude_companies) => patch("exclude_companies", exclude_companies)}
                    />
                  </div>
                  <span className="mt-2 block text-[12px] leading-5 text-muted">
                    Яндекс, Yandex и «Яндекс.Такси» — одно имя. Enter или запятая.
                  </span>
                </label>
                <button
                  type="button"
                  onClick={() => setAdvanced((open) => !open)}
                  className="text-[12px] text-muted hover:text-ink"
                >
                  {advanced ? "скрыть как считаем рынок" : "как считаем рынок"}
                </button>
                {advanced && (
                <div className="grid grid-cols-2 gap-x-8 gap-y-5">
                  <label>
                    <GuideLabel id="thesis.days" className="mb-2 text-[12px] text-muted">
                      Смотреть, дни
                    </GuideLabel>
                    <input
                      className="field-line"
                      type="number"
                      value={form.days}
                      onChange={(e) => patch("days", Number(e.target.value) || 14)}
                    />
                  </label>
                  <label>
                    <GuideLabel id="thesis.min_sample" className="mb-2 text-[12px] text-muted">
                      Мин. вакансий
                    </GuideLabel>
                    <input
                      className="field-line"
                      type="number"
                      value={form.min_sample}
                      onChange={(e) => patch("min_sample", Number(e.target.value) || 8)}
                    />
                  </label>
                  <label>
                    <GuideLabel id="thesis.match" className="mb-2 text-[12px] text-muted">
                      Мин. совпадение с резюме
                    </GuideLabel>
                    <input
                      className="field-line"
                      type="number"
                      value={form.min_median_match}
                      onChange={(e) => patch("min_median_match", Number(e.target.value) || 55)}
                    />
                  </label>
                </div>
                )}
              </div>
              <div className="mt-8 flex items-center gap-5">
                <button type="submit" className="text-[14px] text-accent">
                  {editingId ? "Сохранить" : "Добавить"}
                </button>
                {editingId != null && (
                  <button
                    type="button"
                    onClick={() => {
                      setComposer(false);
                      setEditingId(null);
                      setForm(EMPTY);
                    }}
                    className="text-[14px] text-muted hover:text-ink"
                  >
                    Отмена
                  </button>
                )}
              </div>
            </form>
          ) : waveThesis ? (
            <div className="mx-auto w-full max-w-2xl">
              <WaveDesk thesis={waveThesis} onClose={() => setWaveId(null)} onSent={() => void load()} onOpen={setOpenId} />
            </div>
          ) : selected ? (
            <div className="mx-auto w-full max-w-[440px] pt-6">
              <GuideSpot id="thesis.verdict">
              <p className={`text-[13px] ${verdictTone(selected.stats?.verdict ?? selected.last_verdict)}`}>
                {verdictLabel(selected.stats?.verdict ?? selected.last_verdict)}
                <GuideHint id="thesis.verdict" className="ml-1 inline-flex align-middle" />
              </p>
              <h2 className="mt-2 text-[26px] font-semibold tracking-tight">{selected.name}</h2>
              <p className="mt-2 text-[13px] leading-5 text-muted">
                Фильтр inbox и воронки. В шапке справа можно переключиться на другое направление или показать все карточки.
              </p>
              <p className="mt-3 text-[14px] leading-6 text-muted">
                {selected.stats?.reason || selected.last_reason || "Пока рано: мало вакансий в ленте, чтобы понять рынок."}
              </p>
              {selected.last_wave?.sent_at && (
                <p className="mt-2 text-[13px] text-muted">
                  последняя пачка: написал {selected.last_wave.wrote_count}
                  {relativeTime(selected.last_wave.sent_at) ? ` · ${relativeTime(selected.last_wave.sent_at)}` : ""}
                </p>
              )}
              {pingCount > 0 && <p className="mt-2 text-[13px] text-amber-200">пингануть: {pingCount}</p>}
              {!!selected.exclude_companies?.length && (
                <p className="mt-2 text-[13px] text-muted">
                  кроме: {selected.exclude_companies.join(", ")}
                </p>
              )}

              {selected.stats && (
                <>
                  <div className="mt-8">
                    <div className="mb-2 flex justify-between text-[12px] text-muted">
                      <span>прошло дней</span>
                      <span className="tabular-nums">
                        {selected.stats.age_days} / {selected.stats.window_days} дн.
                      </span>
                    </div>
                    <div className="h-px bg-fill-strong">
                      <div
                        className="h-px bg-accent"
                        style={{
                          width: `${Math.min(100, Math.round((selected.stats.age_days / Math.max(1, selected.stats.window_days)) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                  <dl className="mt-6 divide-y divide-white/[0.06] border-y border-line">
                    {[
                      ["вакансий", String(selected.stats.sample)],
                      ["в inbox", String(selected.stats.inbox ?? 0)],
                      ["типичное совпадение", selected.stats.median_match != null ? String(selected.stats.median_match) : "—"],
                      ["новых за сутки", String(selected.stats.fresh_24h)],
                      ["написал / ответили", `${selected.stats.outreach} / ${selected.stats.replies}`],
                    ].map(([label, value]) => (
                      <div key={label} className="flex items-baseline justify-between gap-4 py-3">
                        <dt className="text-[12px] text-muted">{label}</dt>
                        <dd className="tabular-nums text-[14px]">{value}</dd>
                      </div>
                    ))}
                  </dl>
                    <GuideSpot id="thesis.corridor">
                    <SalaryCorridorBlock huntId={selected.id} threshold={selected.salary_min} />
                  </GuideSpot>
                </>
              )}
              </GuideSpot>

              <div className="mt-8 flex flex-wrap gap-5 text-[14px]">
                <GuideSpot id="thesis.wave" className="inline-flex items-center gap-1">
                <button type="button" className="text-accent" onClick={() => setWaveId(selected.id)}>
                  Написать сегодня
                </button>
                <GuideHint id="thesis.wave" />
                </GuideSpot>
                <button type="button" className="text-muted hover:text-ink" onClick={() => startEdit(selected)}>
                  Изменить
                </button>
                <button
                  type="button"
                  className="text-muted hover:text-rose-200"
                  onClick={async () => {
                    await api.deleteThesis(selected.id);
                    if (activeHuntId === selected.id) await setActiveHuntId(null);
                    setSelectedId(null);
                    await load();
                    await refreshHunts();
                  }}
                >
                  Удалить
                </button>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-[440px] pt-16">
              <p className="text-[22px] font-medium tracking-tight">Пока нет направлений</p>
              <p className="mt-3 text-[14px] leading-6 text-muted">
                Добавь, какие вакансии смотришь — например «Python senior удалёнка». Потом в шапке переключаешься между ними, а Inbox и воронка показывают только это.
              </p>
            </div>
          )}
        </section>
      </div>

      {openId != null && (
        <VacancyDrawer
          vacancyId={openId}
          onClose={() => {
            setOpenId(null);
            void load().catch(() => undefined);
          }}
          onChanged={() => undefined}
        />
      )}
    </div>
  );
}
