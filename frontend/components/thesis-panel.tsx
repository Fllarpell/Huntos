"use client";

import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import type { NudgeOut, Thesis } from "@/lib/types";
import { FilterChips, ToggleChip } from "@/components/filter-chips";
import { FORMATS, LEVELS } from "@/lib/hirehi-filters";
import { WaveDesk } from "@/components/wave-desk";
import { NudgeQueue } from "@/components/nudge-queue";
import { VacancyDrawer } from "@/components/vacancy-drawer";
import { relativeTime } from "@/lib/format";

const EMPTY: Omit<Thesis, "id" | "last_verdict" | "last_reason" | "last_evaluated_at" | "stats" | "enabled"> = {
  name: "Текущий поиск",
  role_query: "",
  grades: [],
  formats: [],
  salary_min: null,
  no_nda: false,
  days: 14,
  min_sample: 8,
  min_median_match: 55,
};

function verdictTone(verdict: string | null | undefined) {
  if (verdict === "alive") return "text-emerald-200";
  if (verdict === "dead") return "text-rose-200";
  return "text-amber-200";
}

function verdictDot(verdict: string | null | undefined) {
  if (verdict === "alive") return "bg-emerald-300";
  if (verdict === "dead") return "bg-rose-300";
  return "bg-amber-300";
}

function verdictLabel(verdict: string | null | undefined) {
  if (verdict === "alive") return "жив";
  if (verdict === "dead") return "мёртв";
  if (verdict === "weak") return "слабо";
  return "нет вердикта";
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

  async function load() {
    const [data, ping] = await Promise.all([api.theses(), api.nudge()]);
    setItems(data);
    setNudge(ping);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, []);

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
      const saved = await api.saveThesis({ ...form, enabled: true, name: form.name }, editingId ?? undefined);
      setStatus(editingId ? "Тезис обновлён" : "Тезис поставлен");
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
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 items-center gap-6 px-7 pt-6 pb-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight">Тезис</h1>
          <p className="mt-0.5 text-[12px] text-muted">
            {items.length ? `${items.length} · гипотеза про сегмент` : "гипотеза: этот сегмент ещё жив"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (composer) {
              setComposer(false);
              setEditingId(null);
              setForm(EMPTY);
            } else startCreate();
          }}
          className={`ml-auto inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] ${
            composer ? "bg-white/10 text-white" : "text-accent hover:bg-accent/10"
          }`}
        >
          {composer ? <X size={14} /> : <Plus size={14} />}
          {composer ? "Закрыть" : "тезис"}
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
        <aside className="w-[280px] shrink-0 overflow-y-auto border-r border-line py-2">
          {items.length === 0 ? (
            <p className="px-5 py-6 text-[13px] text-muted">Пока нет тезиса</p>
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
                  className={`flex w-full items-start gap-3 px-4 py-3 text-left ${
                    active ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"
                  }`}
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
        </aside>

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
                {editingId ? "Изменить тезис" : "Новый тезис"}
              </h2>
              <p className="mt-2 text-[13px] leading-5 text-muted">
                Опиши сегмент, который проверяешь. Через пару недель Hunt скажет, есть ли там живые ответы. Волна — пачка вакансий из Inbox, которым пишешь разом.
              </p>
              <div className="mt-8 space-y-6">
                <label className="block">
                  <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Название</span>
                  <input
                    className="field-line"
                    value={form.name}
                    onChange={(e) => patch("name", e.target.value)}
                    placeholder="Staff frontend remote 400k+"
                    autoFocus
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Запрос</span>
                  <input
                    className="field-line"
                    value={form.role_query}
                    onChange={(e) => patch("role_query", e.target.value)}
                    placeholder="слова из роли, компании или описания"
                  />
                </label>
                <fieldset>
                  <legend className="mb-2 text-[11px] tracking-[0.16em] text-muted uppercase">Грейд</legend>
                  <FilterChips options={LEVELS} value={form.grades} onChange={(grades) => patch("grades", grades)} />
                </fieldset>
                <fieldset>
                  <legend className="mb-2 text-[11px] tracking-[0.16em] text-muted uppercase">Формат</legend>
                  <FilterChips options={FORMATS} value={form.formats} onChange={(formats) => patch("formats", formats)} />
                </fieldset>
                <div className="grid grid-cols-2 gap-x-8 gap-y-5">
                  <label>
                    <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Мин. зп</span>
                    <input
                      className="field-line"
                      type="number"
                      value={form.salary_min ?? ""}
                      onChange={(e) => patch("salary_min", e.target.value ? Number(e.target.value) : null)}
                      placeholder="350000"
                    />
                  </label>
                  <label>
                    <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Ждать, дни</span>
                    <input
                      className="field-line"
                      type="number"
                      value={form.days}
                      onChange={(e) => patch("days", Number(e.target.value) || 14)}
                    />
                  </label>
                  <label>
                    <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Мин. вакансий</span>
                    <input
                      className="field-line"
                      type="number"
                      value={form.min_sample}
                      onChange={(e) => patch("min_sample", Number(e.target.value) || 8)}
                    />
                  </label>
                  <label>
                    <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Мин. совпадение</span>
                    <input
                      className="field-line"
                      type="number"
                      value={form.min_median_match}
                      onChange={(e) => patch("min_median_match", Number(e.target.value) || 55)}
                    />
                  </label>
                </div>
                <ToggleChip label="без NDA" on={form.no_nda} onChange={(no_nda) => patch("no_nda", no_nda)} />
              </div>
              <div className="mt-8 flex items-center gap-5">
                <button type="submit" className="text-[14px] text-accent">
                  {editingId ? "Сохранить" : "Поставить"}
                </button>
                {editingId != null && (
                  <button
                    type="button"
                    onClick={() => {
                      setComposer(false);
                      setEditingId(null);
                      setForm(EMPTY);
                    }}
                    className="text-[14px] text-muted hover:text-white"
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
              <p className={`text-[13px] ${verdictTone(selected.stats?.verdict ?? selected.last_verdict)}`}>
                {verdictLabel(selected.stats?.verdict ?? selected.last_verdict)}
              </p>
              <h2 className="mt-2 text-[26px] font-semibold tracking-tight">{selected.name}</h2>
              <p className="mt-3 text-[14px] leading-6 text-muted">
                {selected.stats?.reason || selected.last_reason || "Пока рано судить — копим ответы."}
              </p>
              {selected.last_wave?.sent_at && (
                <p className="mt-2 text-[13px] text-muted">
                  последняя волна: написал {selected.last_wave.wrote_count}
                  {relativeTime(selected.last_wave.sent_at) ? ` · ${relativeTime(selected.last_wave.sent_at)}` : ""}
                </p>
              )}
              {pingCount > 0 && <p className="mt-2 text-[13px] text-amber-200">пингануть: {pingCount}</p>}

              {selected.stats && (
                <>
                  <div className="mt-8">
                    <div className="mb-2 flex justify-between text-[12px] text-muted">
                      <span>прошло дней</span>
                      <span className="tabular-nums">
                        {selected.stats.age_days} / {selected.stats.window_days} дн.
                      </span>
                    </div>
                    <div className="h-px bg-white/10">
                      <div
                        className="h-px bg-accent"
                        style={{
                          width: `${Math.min(100, Math.round((selected.stats.age_days / Math.max(1, selected.stats.window_days)) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                  <dl className="mt-6 divide-y divide-white/[0.06] border-y border-white/[0.06]">
                    {[
                      ["вакансий", String(selected.stats.sample)],
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
                </>
              )}

              <div className="mt-8 flex flex-wrap gap-5 text-[14px]">
                <button type="button" className="text-accent" onClick={() => setWaveId(selected.id)}>
                  Волна
                </button>
                <button type="button" className="text-muted hover:text-white" onClick={() => startEdit(selected)}>
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
              <p className="text-[22px] font-medium tracking-tight">Пока нет тезиса</p>
              <p className="mt-3 text-[14px] leading-6 text-muted">
                Поставь гипотезу: какой сегмент проверяешь. Через пару недель станет ясно, стоит ли туда идти.
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
