"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { api, type VacancyDraft } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import { adjacentStage, STAGE_LABEL, type CollisionItem, type CompanyContactHint, type CustomFieldDef, type PipelineStage, type Vacancy } from "@/lib/types";
import { FORMATS, LEVELS } from "@/lib/hirehi-filters";
import {
  telegramHandle,
  normalizeTelegramAlias,
  vacancyTelegramUrl,
  normalizeHttpUrl,
  dwellLong,
  dwellStage,
  hasHh,
  hhVacancyUrl,
} from "@/lib/format";
import { MatchBadge } from "./match-badge";
import { TelegramChatLink, ExternalTextLink } from "./telegram-chat-link";
import { ContactBits } from "./contact-bits";
import { SourceBadge } from "./source-badge";
import { VacancySteps } from "./vacancy-steps";
import { CustomFieldInputs } from "./custom-field-inputs";
import { HhPulseMark } from "./hh-pulse-mark";

type Draft = {
  title: string;
  company: string;
  company_inn: string;
  grade: string;
  work_format: string;
  location: string;
  language: string;
  salary_raw: string;
  description: string;
  source_url: string;
  telegram_alias: string;
  contact_email: string;
  contact_phone: string;
  notes: string;
  skillsText: string;
  custom_values: Record<string, string>;
  card_fields: CustomFieldDef[];
};

function fromVacancy(v: Vacancy): Draft {
  return {
    title: v.title ?? "",
    company: v.company ?? "",
    company_inn: v.company_inn ?? "",
    grade: v.grade ?? "",
    work_format: v.work_format ?? "",
    location: v.location ?? "",
    language: v.language ?? "",
    salary_raw: v.salary_raw ?? "",
    description: v.description ?? "",
    source_url: v.source_url ?? "",
    telegram_alias: telegramHandle(v.telegram_alias),
    contact_email: v.contact_email ?? "",
    contact_phone: v.contact_phone ?? "",
    notes: v.notes ?? "",
    skillsText: (v.skills || []).join(", "),
    custom_values: { ...(v.custom_values || {}) },
    card_fields: (v.custom_fields || []).filter((field) => field.scope === "card"),
  };
}

function toPayload(d: Draft): VacancyDraft {
  const innDigits = d.company_inn.replace(/\D/g, "");
  return {
    title: d.title.trim() || "Без названия",
    company: d.company.trim() || null,
    company_inn:
      !innDigits ? null : innDigits.length === 10 || innDigits.length === 12 ? innDigits : undefined,
    grade: d.grade || null,
    work_format: d.work_format || null,
    location: d.location.trim() || null,
    language: d.language.trim() || null,
    salary_raw: d.salary_raw.trim() || null,
    description: d.description,
    source_url: d.source_url.trim() || null,
    telegram_alias: d.telegram_alias,
    contact_email: d.contact_email.trim() || null,
    contact_phone: d.contact_phone.trim() || null,
    notes: d.notes,
    skills: d.skillsText
      .split(/[,;]/)
      .map((s) => s.trim())
      .filter(Boolean),
    custom_values: d.custom_values,
    card_fields: d.card_fields,
  };
}

type DrawerPane = "deal" | "hr" | "more";

const PANES: { id: DrawerPane; label: string }[] = [
  { id: "deal", label: "сделка" },
  { id: "hr", label: "HR" },
  { id: "more", label: "ещё" },
];

function innDraftMatches(draft: string, saved: string | null | undefined): boolean {
  const digits = draft.replace(/\D/g, "");
  const current = (saved || "").replace(/\D/g, "");
  if (!digits) return !current;
  if (digits.length === 10 || digits.length === 12) return digits === current;
  return true;
}

function sameAsVacancy(d: Draft, v: Vacancy): boolean {
  const p = toPayload(d);
  const skills = v.skills || [];
  const nextSkills = p.skills || [];
  return (
    p.title === (v.title || "Без названия") &&
    (p.company || null) === (v.company || null) &&
    innDraftMatches(d.company_inn, v.company_inn) &&
    (p.grade || null) === (v.grade || null) &&
    (p.work_format || null) === (v.work_format || null) &&
    (p.location || null) === (v.location || null) &&
    (p.language || null) === (v.language || null) &&
    (p.salary_raw || null) === (v.salary_raw || null) &&
    (p.description || "") === (v.description || "") &&
    (normalizeHttpUrl(p.source_url) || null) === (v.source_url || null) &&
    (normalizeTelegramAlias(p.telegram_alias) || null) === (v.telegram_alias || null) &&
    (p.contact_email || null) === (v.contact_email || null) &&
    (p.contact_phone || null) === (v.contact_phone || null) &&
    (p.notes || "") === (v.notes || "") &&
    skills.length === nextSkills.length &&
    skills.every((s, i) => s === nextSkills[i]) &&
    sameValues(d.custom_values, v.custom_values || {}) &&
    sameCardFields(d.card_fields, v.custom_fields || [])
  );
}

function sameCardFields(local: CustomFieldDef[], all: CustomFieldDef[]) {
  const saved = all.filter((field) => field.scope === "card");
  if (local.length !== saved.length) return false;
  return local.every((field, i) => field.id === saved[i]?.id && field.name === saved[i]?.name && field.kind === saved[i]?.kind);
}

function sameValues(a: Record<string, string>, b: Record<string, string>) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    if ((a[key] || "") !== (b[key] || "")) return false;
  }
  return true;
}

export function VacancyDrawer({
  vacancyId,
  onClose,
  onChanged,
  initialPane = "deal",
}: {
  vacancyId: number;
  onClose: () => void;
  onChanged: (v: Vacancy) => void;
  initialPane?: DrawerPane;
}) {
  const [vacancy, setVacancy] = useState<Vacancy | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upcoming, setUpcoming] = useState<CollisionItem[]>([]);
  const [pane, setPane] = useState<DrawerPane>(initialPane);
  const [jdOpen, setJdOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { hunts, activeHuntId, activeHunt, refresh: refreshHunts } = useHunt();

  useEffect(() => {
    setError(null);
    setDraft(null);
    setPane(initialPane === "hr" ? "hr" : initialPane === "more" ? "more" : "deal");
    setJdOpen(false);
    api.vacancy(vacancyId).then((v) => {
      setVacancy(v);
      setDraft(fromVacancy(v));
    });
    api
      .collisions()
      .then((cal) => setUpcoming(cal.upcoming))
      .catch(() => setUpcoming([]));
  }, [vacancyId, initialPane]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0);
  }, [pane]);

  useEffect(() => {
    if (!vacancy || !draft || sameAsVacancy(draft, vacancy)) return;
    const t = setTimeout(() => {
      void api
        .patchVacancy(vacancy.id, toPayload(draft))
        .then((saved) => {
          setVacancy(saved);
          onChanged(saved);
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Не сохранилось"));
    }, 700);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, vacancy]);

  function patch(part: Partial<Draft>) {
    setDraft((prev) => (prev ? { ...prev, ...part } : prev));
  }

  async function addCustomField(field: CustomFieldDef, scope: "card" | "hunt") {
    if (!vacancy || !draft) return;
    setError(null);
    try {
      if (scope === "hunt") {
        const targetId =
          activeHuntId ??
          vacancy.hunts?.find((item) => item.matched || item.pinned)?.id ??
          hunts[0]?.id;
        if (!targetId) {
          const hunt = (vacancy.custom_fields || []).filter((item) => item.scope !== "card");
          await api.saveProfile({ custom_fields: [...hunt, { ...field, scope: "hunt" }] });
        } else {
          const schema = hunts.find((item) => item.id === targetId)?.custom_fields || [];
          await api.saveHuntFields(targetId, [...schema, { ...field, scope: "hunt" }]);
          const pinned = (vacancy.hunts || []).filter((item) => item.pinned).map((item) => item.id);
          if (!pinned.includes(targetId) && !(vacancy.hunts || []).some((item) => item.id === targetId && item.matched)) {
            await api.setVacancyHunts(vacancy.id, [...pinned, targetId]);
          }
          await refreshHunts();
        }
        const fresh = await api.vacancy(vacancy.id);
        setVacancy(fresh);
        setDraft((prev) => (prev ? { ...prev, card_fields: (fresh.custom_fields || []).filter((item) => item.scope === "card") } : prev));
        onChanged(fresh);
        return;
      }
      setVacancy({
        ...vacancy,
        custom_fields: [...(vacancy.custom_fields || []), { ...field, scope: "card" }],
      });
      patch({ card_fields: [...draft.card_fields, { ...field, scope: "card" }] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Поле не добавилось");
    }
  }

  function removeCardField(id: string) {
    if (!vacancy || !draft) return;
    setVacancy({
      ...vacancy,
      custom_fields: (vacancy.custom_fields || []).filter((item) => item.id !== id),
    });
    const nextValues = { ...draft.custom_values };
    delete nextValues[id];
    patch({
      card_fields: draft.card_fields.filter((item) => item.id !== id),
      custom_values: nextValues,
    });
  }

  async function toggleHunt(id: number) {
    if (!vacancy) return;
    const refs = vacancy.hunts || [];
    const current = refs.find((item) => item.id === id);
    if (current?.matched) return;
    const pinned = refs.filter((item) => item.pinned).map((item) => item.id);
    const next = pinned.includes(id) ? pinned.filter((item) => item !== id) : [...pinned, id];
    setBusy("hunt");
    setError(null);
    try {
      const fresh = await api.setVacancyHunts(vacancy.id, next);
      setVacancy(fresh);
      onChanged(fresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Охота не обновилась");
    } finally {
      setBusy(null);
    }
  }

  async function setStage(stage: PipelineStage) {
    if (!vacancy || vacancy.pipeline_stage === stage) return;
    setBusy("stage");
    setError(null);
    try {
      const next = await api.setStage(vacancy.id, stage, undefined, activeHuntId);
      setVacancy(next);
      onChanged(next);
      if (stage === "inbox" || stage === "trash") onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сдвинулось");
    } finally {
      setBusy(null);
    }
  }

  const gradeOptions = useMemo(() => {
    const extra = draft?.grade && !LEVELS.some((l) => l.value === draft.grade) ? [{ value: draft.grade, label: draft.grade }] : [];
    return extra.concat([...LEVELS]);
  }, [draft?.grade]);

  const formatOptions = useMemo(() => {
    const extra =
      draft?.work_format && !FORMATS.some((f) => f.value === draft.work_format)
        ? [{ value: draft.work_format, label: draft.work_format }]
        : [];
    return extra.concat([...FORMATS]);
  }, [draft?.work_format]);

  if (!vacancy || !draft) {
    return (
      <div className="fixed inset-y-0 right-0 z-40 w-[min(560px,100%)] border-l border-line bg-bg-soft p-8">
        <p className="text-muted">Загрузка…</p>
      </div>
    );
  }

  const chatUrl = vacancyTelegramUrl({ telegram_alias: draft.telegram_alias, telegram_url: vacancy.telegram_url });
  const pageUrl = normalizeHttpUrl(draft.source_url);

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <section
        className="flex h-full w-[min(560px,100%)] flex-col border-l border-line bg-bg-soft shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-4 border-b border-line px-7 py-5">
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <MatchBadge score={vacancy.match_score} status={vacancy.scoring_status} />
              <SourceBadge source={vacancy.source} />
            </div>
            <div className="flex gap-2">
              <input
                value={draft.company}
                onChange={(e) => patch({ company: e.target.value })}
                placeholder="Компания"
                className="min-w-0 flex-1 !py-1.5"
              />
              <input
                value={draft.company_inn}
                onChange={(e) => patch({ company_inn: e.target.value.replace(/\D/g, "").slice(0, 12) })}
                placeholder="ИНН"
                inputMode="numeric"
                autoComplete="off"
                className="w-[9rem] shrink-0 !py-1.5"
              />
            </div>
            <input
              value={draft.title}
              onChange={(e) => patch({ title: e.target.value })}
              placeholder="Роль / название вакансии"
              className="text-xl font-semibold tracking-tight !py-2"
            />
            <div className="grid grid-cols-2 gap-2">
              <select value={draft.grade} onChange={(e) => patch({ grade: e.target.value })}>
                <option value="">грейд</option>
                {gradeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <select value={draft.work_format} onChange={(e) => patch({ work_format: e.target.value })}>
                <option value="">формат</option>
                {formatOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                value={draft.salary_raw}
                onChange={(e) => patch({ salary_raw: e.target.value })}
                placeholder="зп, например 300 000–400 000"
              />
              <input
                value={draft.language}
                onChange={(e) => patch({ language: e.target.value })}
                placeholder="язык"
              />
            </div>
            <input
              value={draft.location}
              onChange={(e) => patch({ location: e.target.value })}
              placeholder="локация / страна"
            />
            <ContactBits
              vacancy={{
                telegram_alias: draft.telegram_alias,
                telegram_url: chatUrl,
                contact_email: draft.contact_email,
                contact_phone: draft.contact_phone,
              }}
              className="text-[13px]"
            />
            {pageUrl && <ExternalTextLink href={pageUrl} className="block text-[13px]" />}
            {!!vacancy.extra_sources?.length && (
              <div className="flex flex-wrap gap-1">
                {vacancy.extra_sources.map((src) => (
                  <SourceBadge key={`${src.source}-${src.source_id}`} source={src.source} />
                ))}
              </div>
            )}
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-muted hover:bg-white/6 hover:text-white">
            <X size={18} />
          </button>
        </header>

        <nav className="flex shrink-0 items-center gap-5 border-b border-white/[0.06] px-7">
          {PANES.map((item) => {
            const mark =
              item.id === "hr" &&
              Boolean(draft.telegram_alias || draft.contact_email || draft.contact_phone);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setPane(item.id)}
                className={`border-b pb-2.5 pt-3 text-[13px] ${
                  pane === item.id
                    ? "border-accent text-white"
                    : "border-transparent text-muted hover:text-white/80"
                }`}
              >
                {item.label}
                {mark ? <span className="ml-1.5 inline-block h-1 w-1 rounded-full bg-accent" /> : null}
              </button>
            );
          })}
        </nav>

        <div ref={scrollRef} className="flex-1 space-y-8 overflow-y-auto px-7 py-6">
          {error && <p className="rounded-xl bg-rose-400/10 px-3 py-2 text-sm text-rose-200">{error}</p>}

          <section>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 className="text-[12px] text-muted">вакансия</h3>
              {draft.description.trim() ? (
                <button
                  type="button"
                  className="text-[12px] text-muted hover:text-white"
                  onClick={() => setJdOpen((open) => !open)}
                >
                  {jdOpen ? "свернуть" : "полностью"}
                </button>
              ) : null}
            </div>
            {jdOpen || !draft.description.trim() ? (
              <>
                <textarea
                  rows={jdOpen ? 14 : 5}
                  value={draft.description}
                  onChange={(e) => patch({ description: e.target.value })}
                  placeholder="Описание, задачи, требования…"
                />
                <label className="mt-3 mb-1.5 block text-[12px] text-muted">Скиллы через запятую</label>
                <input
                  value={draft.skillsText}
                  onChange={(e) => patch({ skillsText: e.target.value })}
                  placeholder="python, fastapi, ml"
                />
              </>
            ) : (
              <button type="button" className="w-full text-left" onClick={() => setJdOpen(true)}>
                <p className="line-clamp-5 whitespace-pre-wrap text-[14px] leading-6 text-white/80">
                  {draft.description}
                </p>
                {draft.skillsText ? (
                  <p className="mt-2 line-clamp-2 text-[12px] text-muted">{draft.skillsText}</p>
                ) : null}
              </button>
            )}
          </section>

          {pane === "deal" && (
            <>
          <section className="flex flex-wrap items-center gap-2">
            {(() => {
              const left = adjacentStage(vacancy.pipeline_stage, -1);
              const right = adjacentStage(vacancy.pipeline_stage, 1);
              return (
                <>
                  <button
                    type="button"
                    disabled={!left || busy === "stage"}
                    className="flex items-center gap-1 rounded-xl bg-white/8 px-3 py-1.5 text-sm disabled:opacity-30"
                    onClick={() => left && void setStage(left)}
                  >
                    <ChevronLeft size={14} />
                    {left ? STAGE_LABEL[left] : "край"}
                  </button>
                  <span className="flex items-baseline gap-2">
                    <span className="text-[13px] text-muted">{STAGE_LABEL[vacancy.pipeline_stage]}</span>
                    {dwellStage(vacancy.pipeline_stage) && vacancy.dwell_days != null && (
                      <span
                        className={`text-[12px] tabular-nums ${vacancy.dwell_stale ? "text-amber-200" : "text-white/40"}`}
                      >
                        {dwellLong(vacancy.dwell_days)}
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    disabled={!right || busy === "stage"}
                    className="flex items-center gap-1 rounded-xl bg-white/8 px-3 py-1.5 text-sm disabled:opacity-30"
                    onClick={() => right && void setStage(right)}
                  >
                    {right ? STAGE_LABEL[right] : "край"}
                    <ChevronRight size={14} />
                  </button>
                  {vacancy.pipeline_stage !== "inbox" && (
                    <button
                      type="button"
                      disabled={busy === "stage"}
                      className="rounded-xl px-3 py-1.5 text-sm text-muted hover:text-white"
                      onClick={() => void setStage("inbox")}
                    >
                      В inbox
                    </button>
                  )}
                  {vacancy.pipeline_stage !== "rejected" && vacancy.pipeline_stage !== "trash" && (
                    <button
                      type="button"
                      disabled={busy === "stage"}
                      className="rounded-xl px-3 py-1.5 text-sm text-rose-200/80 hover:text-rose-100"
                      onClick={() => void setStage("rejected")}
                    >
                      Отказ
                    </button>
                  )}
                </>
              );
            })()}
          </section>

          <VacancySteps
            vacancy={vacancy}
            upcoming={upcoming}
            onChanged={(saved) => {
              setVacancy(saved);
              onChanged(saved);
              void api.collisions().then((cal) => setUpcoming(cal.upcoming));
            }}
            onError={(message) => setError(message)}
          />
            </>
          )}

          {pane === "hr" && (
          <section>
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-[12px] text-muted">контакт</h3>
              <Link href="/contacts" className="text-[12px] text-accent hover:underline">
                Весь пул
              </Link>
            </div>
            {(vacancy.company_contacts || []).length > 0 && (
              <div className="mb-3 space-y-2 rounded-2xl border border-accent/20 bg-accent/8 px-3 py-3">
                <p className="text-[12px] text-accent">В этой компании уже есть HR</p>
                {(vacancy.company_contacts || []).map((hint: CompanyContactHint) => (
                  <div key={hint.label + String(hint.vacancy_id)} className="flex flex-wrap items-center gap-2">
                    <ContactBits
                      vacancy={{
                        telegram_alias: hint.telegram_alias || null,
                        telegram_url: null,
                        contact_email: hint.contact_email,
                        contact_phone: hint.contact_phone,
                      }}
                    />
                    <button
                      type="button"
                      className="rounded-lg bg-accent/20 px-2 py-1 text-[11px] text-accent"
                      onClick={() =>
                        patch({
                          telegram_alias: draft.telegram_alias || telegramHandle(hint.telegram_alias),
                          contact_email: draft.contact_email || hint.contact_email || "",
                          contact_phone: draft.contact_phone || hint.contact_phone || "",
                        })
                      }
                    >
                      Подставить
                    </button>
                    {hint.vacancy_id != null && hint.vacancy_id !== vacancy.id && (
                      <span className="text-[11px] text-muted">{hint.title}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            <label className="mb-1.5 block text-[12px] text-muted">Telegram</label>
            <input
              value={draft.telegram_alias}
              onChange={(e) => patch({ telegram_alias: e.target.value })}
              placeholder="@username"
              autoComplete="off"
              spellCheck={false}
            />
            <label className="mt-3 mb-1.5 block text-[12px] text-muted">Email</label>
            <input
              value={draft.contact_email}
              onChange={(e) => patch({ contact_email: e.target.value })}
              placeholder="name@company.com"
              autoComplete="off"
              spellCheck={false}
            />
            <label className="mt-3 mb-1.5 block text-[12px] text-muted">Телефон</label>
            <input
              value={draft.contact_phone}
              onChange={(e) => patch({ contact_phone: e.target.value })}
              placeholder="+7 999 000-00-00"
              autoComplete="off"
              spellCheck={false}
            />
            <label className="mt-3 mb-1.5 block text-[12px] text-muted">Чат</label>
            {chatUrl ? (
              <TelegramChatLink
                href={chatUrl}
                className="flex w-full items-center rounded-[10px] border border-line bg-[#0e1015] px-3 py-2.5 text-[14px]"
              />
            ) : (
              <p className="rounded-[10px] border border-dashed border-line px-3 py-2.5 text-[14px] text-muted">
                t.me/… появится, когда введёшь @username
              </p>
            )}
          </section>
          )}

          {pane === "deal" && vacancy.pipeline_stage === "waiting" && (
            <section
              className={
                vacancy.ping_due
                  ? "rounded-2xl border border-amber-400/20 bg-amber-400/8 p-4"
                  : undefined
              }
            >
              <h3
                className={`mb-3 text-[12px] ${
                  vacancy.ping_due ? "text-amber-200/80" : "text-muted"
                }`}
              >
                Пинг
              </h3>
              <p
                className={`text-[13px] leading-5 ${vacancy.ping_due ? "text-amber-50" : "text-muted"}`}
              >
                {vacancy.ping_due
                  ? `Эйчар молчит ${vacancy.silence_days ?? 5} дн. Напиши ещё раз — карточка останется в «жду ответа».`
                  : "Если эйчар не ответит 5 дней, карточка появится в очереди «пингануть». Стадия не сменится."}
              </p>
              <button
                type="button"
                disabled={busy === "ping"}
                className="mt-3 rounded-xl bg-amber-400/20 px-3 py-1.5 text-sm text-amber-100 disabled:opacity-40"
                onClick={async () => {
                  setBusy("ping");
                  setError(null);
                  try {
                    const next = await api.markPinged(vacancy.id);
                    setVacancy(next);
                    onChanged(next);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Не отметилось");
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                {busy === "ping" ? "Отмечаю…" : "Пинганул"}
              </button>
            </section>
          )}

          {pane === "deal" && (hasHh(vacancy) || vacancy.hh_pulse) && (
            <section
              className={
                vacancy.hh_pulse === "discarded"
                  ? "rounded-2xl border border-rose-400/20 bg-rose-400/8 p-4"
                  : vacancy.hh_pulse === "invited"
                    ? "rounded-2xl border border-emerald-400/20 bg-emerald-400/8 p-4"
                    : undefined
              }
            >
              <h3
                className={`mb-3 text-[12px] ${
                  vacancy.hh_pulse === "discarded"
                    ? "text-rose-200/80"
                    : vacancy.hh_pulse === "invited"
                      ? "text-emerald-200/80"
                      : "text-muted"
                }`}
              >
                hh
              </h3>
              <p
                className={`text-[13px] leading-5 ${
                  vacancy.hh_pulse === "discarded"
                    ? "text-rose-50"
                    : vacancy.hh_pulse === "invited"
                      ? "text-emerald-50"
                      : "text-muted"
                }`}
              >
                {vacancy.hh_pulse
                  ? "Колонку на воронке это не двигает. Сдвинь сам, если это уже скрин, собес или отказ."
                  : "Отметь приглашение или отказ с hh. Hunt сам в твой аккаунт не заходит."}
              </p>
              {vacancy.hh_pulse && (
                <p className="mt-2">
                  <HhPulseMark pulse={vacancy.hh_pulse} className="text-[13px]" />
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy === "hh"}
                  className="rounded-xl bg-emerald-400/15 px-3 py-1.5 text-sm text-emerald-100 disabled:opacity-40"
                  onClick={async () => {
                    setBusy("hh");
                    setError(null);
                    try {
                      const next = await api.markHhPulse(vacancy.id, "invited");
                      setVacancy(next);
                      onChanged(next);
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Не отметилось");
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  {busy === "hh" ? "Отмечаю…" : "Пригласил"}
                </button>
                <button
                  type="button"
                  disabled={busy === "hh"}
                  className="rounded-xl bg-rose-400/15 px-3 py-1.5 text-sm text-rose-100 disabled:opacity-40"
                  onClick={async () => {
                    setBusy("hh");
                    setError(null);
                    try {
                      const next = await api.markHhPulse(vacancy.id, "discarded");
                      setVacancy(next);
                      onChanged(next);
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Не отметилось");
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  Отказал
                </button>
                {vacancy.hh_pulse && (
                  <button
                    type="button"
                    disabled={busy === "hh"}
                    className="rounded-xl px-3 py-1.5 text-sm text-muted hover:text-white disabled:opacity-40"
                    onClick={async () => {
                      setBusy("hh");
                      setError(null);
                      try {
                        const next = await api.markHhPulse(vacancy.id, null);
                        setVacancy(next);
                        onChanged(next);
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Не отметилось");
                      } finally {
                        setBusy(null);
                      }
                    }}
                  >
                    Снять
                  </button>
                )}
                {hhVacancyUrl(vacancy) && (
                  <a
                    href={hhVacancyUrl(vacancy) || ""}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-xl px-3 py-1.5 text-sm text-muted hover:text-white"
                  >
                    открыть на hh
                  </a>
                )}
              </div>
            </section>
          )}

          {pane === "more" && (
          <section>
            <h3 className="mb-3 text-[12px] text-muted">ссылка на вакансию</h3>
            <input
              value={draft.source_url}
              onChange={(e) => patch({ source_url: e.target.value })}
              placeholder="https://hirehi.ru/… или любая ссылка"
            />
            {pageUrl && (
              <ExternalTextLink
                href={pageUrl}
                className="mt-2 flex w-full items-center rounded-[10px] border border-line bg-[#0e1015] px-3 py-2.5 text-[14px]"
              />
            )}
            {!!vacancy.extra_sources?.length && (
              <div className="mt-4 flex flex-wrap gap-1">
                {vacancy.extra_sources.map((src) => (
                  <SourceBadge key={`${src.source}-${src.source_id}`} source={src.source} />
                ))}
              </div>
            )}
            <p className="mt-6 text-[13px] text-muted">
              Общие поля охоты
              {activeHunt ? ` «${activeHunt.name}»` : ""} можно править в{" "}
              <Link href="/settings?tab=fields" className="text-accent hover:underline">
                настройках
              </Link>
              .
            </p>
          </section>
          )}

          {pane === "deal" && (
          <>
          {hunts.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-[12px] text-muted">охоты</h3>
              <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                {hunts.map((hunt) => {
                  const ref = (vacancy.hunts || []).find((item) => item.id === hunt.id);
                  const on = Boolean(ref?.matched || ref?.pinned);
                  return (
                    <button
                      key={hunt.id}
                      type="button"
                      disabled={busy === "hunt" || ref?.matched}
                      onClick={() => void toggleHunt(hunt.id)}
                      className={`border-b pb-0.5 text-[13px] ${
                        on ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
                      } disabled:opacity-60`}
                      title={ref?.matched ? "подошла по тезису этой охоты" : "показать карточку в этой охоте"}
                    >
                      {hunt.name}
                      {ref?.matched ? " · тезис" : ""}
                    </button>
                  );
                })}
              </div>
            </section>
          )}
          <CustomFieldInputs
            fields={vacancy.custom_fields || []}
            values={draft.custom_values}
            onChange={(custom_values) => patch({ custom_values })}
            onAdd={(field, scope) => void addCustomField(field, scope)}
            onRemoveCard={removeCardField}
          />
          <section>
            <h3 className="mb-3 text-[12px] text-muted">заметки</h3>
            <textarea
              rows={5}
              value={draft.notes}
              onChange={(e) => patch({ notes: e.target.value })}
              placeholder="Дедлайн тестового, впечатление, договорённости…"
            />
          </section>
          </>
          )}
        </div>
      </section>
    </div>
  );
}
