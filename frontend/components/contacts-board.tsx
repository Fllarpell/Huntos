"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, Mail, Phone, Plus, Send, X } from "lucide-react";
import { api } from "@/lib/api";
import type { HuntContact } from "@/lib/types";
import { STAGE_LABEL } from "@/lib/types";
import { normalizeInn, ruCount, telegramHandle, telegramUrl, telHref } from "@/lib/format";
import { CompanyMark } from "./company-mark";
import { SearchField } from "./search-field";
import { VacancyDrawer } from "./vacancy-drawer";
import { useWorkspace } from "@/components/workspace-context";

const EMPTY = { company: "", company_inn: "", telegram_alias: "", contact_email: "", contact_phone: "" };

type HuntCompany = HuntContact["companies"][number];
type View = "people" | "companies";

function personTitle(person: HuntContact): string {
  return telegramHandle(person.telegram_alias) || person.contact_email || person.contact_phone || person.label;
}

function personMark(person: HuntContact): string {
  const title = personTitle(person).replace(/^@/, "").trim();
  return (title.slice(0, 1) || "?").toUpperCase();
}

function isNdaName(name: string | null | undefined): boolean {
  const compact = (name || "").trim().toLowerCase().replace(/[.\s]+/g, "");
  return compact === "nda" || compact === "нда";
}

function companyGroups(people: HuntContact[]) {
  const map = new Map<string, { org: HuntCompany; people: HuntContact[] }>();
  for (const person of people) {
    const orgs = person.companies.length
      ? person.companies
      : [
          {
            name: null,
            inn: null,
            label: "без компании",
            org_key: `none:${person.id}`,
            company_icon: null,
            card_count: 0,
            saved: true,
          },
        ];
    for (const org of orgs) {
      const k = org.org_key || `fallback:${org.inn || ""}:${(org.name || "").toLowerCase()}:${person.id}`;
      const slot = map.get(k);
      if (slot) {
        if (!slot.people.some((row) => row.id === person.id)) slot.people.push(person);
        if (org.company_icon && !slot.org.company_icon) {
          slot.org = { ...slot.org, company_icon: org.company_icon };
        }
      } else {
        map.set(k, { org: { ...org }, people: [person] });
      }
    }
  }
  return [...map.values()].sort((a, b) =>
    (a.org.label || a.org.name || "").localeCompare(b.org.label || b.org.name || "", "ru"),
  );
}

function cardInOrg(card: HuntContact["cards"][number], org: HuntCompany): boolean {
  const inn = normalizeInn(org.inn);
  const cardInn = normalizeInn(card.company_inn);
  if (inn) return cardInn === inn;
  if (org.org_key?.startsWith("anon:v:")) return org.org_key === `anon:v:${card.id}`;
  return (card.company || "").trim().toLowerCase() === (org.name || "").trim().toLowerCase();
}

function markTone(seed: string): string {
  let n = 0;
  for (let i = 0; i < seed.length; i += 1) n = (n + seed.charCodeAt(i) * 19) % 4;
  return [
    "bg-accent/14 text-accent",
    "bg-[#c4b49a]/16 text-[#e4d4bc]",
    "bg-[#9bb0c8]/16 text-[#c8d6e6]",
    "bg-[#b3c2a6]/16 text-[#d4e0c8]",
  ][n];
}

function companyLine(org: HuntCompany): string {
  return (org.name || "").trim() || "без компании";
}

function CopyBtn({ value, copied, onCopy }: { value: string; copied: boolean; onCopy: (value: string) => void }) {
  return (
    <button
      type="button"
      title="Копировать"
      onClick={() => onCopy(value)}
      className="rounded-md p-1.5 text-muted opacity-0 transition group-hover/row:opacity-100 hover:bg-white/8 hover:text-white"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

function FieldRow({
  icon: Icon,
  label,
  value,
  href,
  copied,
  onCopy,
}: {
  icon: typeof Send;
  label: string;
  value: string;
  href?: string | null;
  copied: boolean;
  onCopy: (value: string) => void;
}) {
  const body = (
    <>
      <span className="w-24 shrink-0 text-[12px] text-muted">{label}</span>
      <span className="min-w-0 flex-1 truncate text-[14px] text-white/90">{value}</span>
    </>
  );
  return (
    <div className="group/row flex items-center gap-3 py-3">
      <Icon size={15} strokeWidth={1.7} className="shrink-0 text-muted" />
      {href ? (
        <a
          href={href}
          target={href.startsWith("http") ? "_blank" : undefined}
          rel={href.startsWith("http") ? "noreferrer" : undefined}
          className="flex min-w-0 flex-1 items-center gap-3 hover:text-accent"
        >
          {body}
        </a>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-3">{body}</div>
      )}
      <CopyBtn value={value} copied={copied} onCopy={onCopy} />
    </div>
  );
}

function PersonDetail({
  person,
  org,
  compact,
  busy,
  copied,
  allPool,
  onCopy,
  onOpen,
  onRemove,
}: {
  person: HuntContact;
  org?: HuntCompany;
  compact?: boolean;
  busy: boolean;
  copied: string | null;
  allPool?: boolean;
  onCopy: (value: string) => void;
  onOpen: (id: number) => void;
  onRemove: (ids: number[]) => void;
}) {
  const title = personTitle(person);
  const tg = telegramUrl(person.telegram_alias);
  const handle = telegramHandle(person.telegram_alias);
  const email = (person.contact_email || "").trim();
  const phone = (person.contact_phone || "").trim();
  const poolOnly = person.saved_ids.length > 0 && person.card_count === 0;
  const cards = org ? person.cards.filter((card) => cardInOrg(card, org)) : person.cards;
  const companies = org ? [org] : person.companies;

  return (
    <div className={compact ? "" : "mx-auto w-full max-w-[440px] pt-6"}>
      <div
        className={`flex items-center justify-center rounded-full font-medium ${markTone(title)} ${
          compact ? "h-10 w-10 text-[13px]" : "h-[4.5rem] w-[4.5rem] text-[22px]"
        }`}
      >
        {personMark(person)}
      </div>
      <h2 className={`font-semibold tracking-tight ${compact ? "mt-4 text-[18px]" : "mt-6 text-[26px]"}`}>
        {title}
      </h2>
      {person.owner_email ? (
        <p className={`${compact ? "mt-1" : "mt-2"} text-[13px] text-muted`}>{person.owner_email}</p>
      ) : null}
      {poolOnly && !allPool && (
        <button
          type="button"
          disabled={busy}
          className="mt-2 text-[13px] text-rose-200/70 hover:text-rose-100"
          onClick={() => onRemove(person.saved_ids)}
        >
          Убрать из пула
        </button>
      )}

      <div className="mt-8 divide-y divide-white/[0.06] border-y border-white/[0.06]">
        {handle && (
          <FieldRow
            icon={Send}
            label="Telegram"
            value={handle}
            href={tg}
            copied={copied === handle}
            onCopy={onCopy}
          />
        )}
        {email && (
          <FieldRow
            icon={Mail}
            label="Почта"
            value={email}
            href={`mailto:${email}`}
            copied={copied === email}
            onCopy={onCopy}
          />
        )}
        {phone && (
          <FieldRow
            icon={Phone}
            label="Телефон"
            value={phone}
            href={telHref(phone)}
            copied={copied === phone}
            onCopy={onCopy}
          />
        )}
      </div>

      {companies.length > 0 && !org && (
        <section className="mt-10">
          <p className="text-[11px] tracking-[0.16em] text-muted uppercase">Компания</p>
          <ul className="mt-4 space-y-4">
            {companies.map((company) => (
              <li
                key={company.org_key || company.label || company.name || "x"}
                className="flex items-start gap-3"
              >
                <CompanyMark company={company.name} icon={company.company_icon} size={28} />
                <div className="min-w-0">
                  <p className={`text-[16px] leading-5 ${isNdaName(company.name) ? "text-white/70" : ""}`}>
                    {companyLine(company)}
                  </p>
                  {normalizeInn(company.inn) ? (
                    <p className="mt-1 text-[12px] tabular-nums text-muted">ИНН {normalizeInn(company.inn)}</p>
                  ) : isNdaName(company.name) ? (
                    <p className="mt-1 text-[12px] text-muted">без ИНН</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {cards.length > 0 && (
        <section className="mt-10">
          <p className="text-[11px] tracking-[0.16em] text-muted uppercase">Карточки</p>
          <ul className="mt-3">
            {cards.map((card) => (
              <li key={card.id} className="border-b border-white/[0.06] last:border-0">
                {allPool ? (
                  <div className="flex w-full items-baseline justify-between gap-4 py-3">
                    <span className="min-w-0 truncate text-[14px]">{card.title}</span>
                    <span className="shrink-0 text-[12px] text-muted">{STAGE_LABEL[card.pipeline_stage]}</span>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => onOpen(card.id)}
                    className="flex w-full items-baseline justify-between gap-4 py-3 text-left"
                  >
                    <span className="min-w-0 truncate text-[14px]">{card.title}</span>
                    <span className="shrink-0 text-[12px] text-muted">{STAGE_LABEL[card.pipeline_stage]}</span>
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function ContactsBoard() {
  const { me, asUserId } = useWorkspace();
  const [items, setItems] = useState<HuntContact[]>([]);
  const [q, setQ] = useState("");
  const [view, setView] = useState<View>("people");
  const [pool, setPool] = useState<"mine" | "all">("mine");
  const [form, setForm] = useState(EMPTY);
  const [composer, setComposer] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedOrg, setSelectedOrg] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await api.contacts(q || undefined, pool === "all" ? "all" : undefined));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не загрузилось");
    } finally {
      setLoaded(true);
    }
  }, [q, pool, asUserId]);

  useEffect(() => {
    const t = setTimeout(() => void load(), q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const groups = useMemo(() => companyGroups(items), [items]);
  const person = items.find((row) => row.id === selectedId) ?? items[0] ?? null;
  const group = groups.find((row) => (row.org.org_key || row.org.label) === selectedOrg) ?? groups[0] ?? null;
  const canAdd = Boolean(form.telegram_alias.trim() || form.contact_email.trim() || form.contact_phone.trim());

  useEffect(() => {
    if (view === "people") {
      if (!selectedId || !items.some((row) => row.id === selectedId)) {
        setSelectedId(items[0]?.id ?? null);
      }
      return;
    }
    const keys = groups.map((row) => row.org.org_key || row.org.label || "");
    if (!selectedOrg || !keys.includes(selectedOrg)) {
      setSelectedOrg(keys[0] || null);
    }
  }, [view, items, groups, selectedId, selectedOrg]);

  async function add() {
    const inn = form.company_inn.replace(/\D/g, "");
    if (inn && inn.length !== 10 && inn.length !== 12) {
      setError("ИНН — 10 или 12 цифр");
      return;
    }
    if (!canAdd) {
      setError("Нужен Telegram, email или телефон");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api.saveContact({
        company: form.company || null,
        company_inn: inn || null,
        telegram_alias: form.telegram_alias || null,
        contact_email: form.contact_email || null,
        contact_phone: form.contact_phone || null,
      });
      setForm(EMPTY);
      setComposer(false);
      setView("people");
      setSelectedId(saved.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сохранилось");
    } finally {
      setBusy(false);
    }
  }

  async function removeSaved(ids: number[]) {
    setBusy(true);
    try {
      for (const id of ids) await api.deleteSavedContact(id);
      setSelectedId(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалилось");
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      window.setTimeout(() => setCopied((cur) => (cur === value ? null : cur)), 1200);
    } catch {
      setError("Не скопировалось");
    }
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 items-center gap-6 px-7 pt-6 pb-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight">Контакты</h1>
          <p className="mt-0.5 text-[12px] text-muted">
            {loaded ? ruCount(items.length, "человек", "человека", "человек") : "…"}
            {pool === "all" ? " · все аккаунты" : q ? " по запросу" : ""}
          </p>
        </div>
        <div className="flex items-center gap-5 text-[13px]">
          {(
            [
              ["people", "люди"],
              ["companies", "компании"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setView(value);
                setComposer(false);
              }}
              className={`border-b pb-0.5 ${
                view === value && !composer
                  ? "border-accent text-white"
                  : "border-transparent text-muted hover:text-white/80"
              }`}
            >
              {label}
            </button>
          ))}
          {me?.is_host && (
            <button
              type="button"
              onClick={() => {
                setPool((p) => (p === "all" ? "mine" : "all"));
                setComposer(false);
              }}
              className={`border-b pb-0.5 ${
                pool === "all" ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
              }`}
            >
              все
            </button>
          )}
        </div>
        {pool !== "all" && (
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setComposer((open) => !open);
                setError(null);
              }}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] ${
                composer ? "bg-white/10 text-white" : "text-accent hover:bg-accent/10"
              }`}
            >
              {composer ? <X size={14} /> : <Plus size={14} />}
              {composer ? "Закрыть" : "HR"}
            </button>
          </div>
        )}
      </header>

      {error && (
        <p className="mx-7 mb-3 rounded-xl border border-rose-400/20 bg-rose-400/8 px-4 py-2.5 text-sm text-rose-100">
          {error}
        </p>
      )}

      <div className="flex min-h-0 flex-1 border-t border-line">
        <aside className="flex w-[300px] shrink-0 flex-col border-r border-line">
          <div className="border-b border-line px-3 py-3">
            <SearchField className="w-full" value={q} onChange={setQ} placeholder="имя, компания, @hr" />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-2">
            {!loaded ? (
              <p className="px-5 py-6 text-[13px] text-muted">Загрузка…</p>
            ) : items.length === 0 ? (
              <p className="px-5 py-6 text-[13px] text-muted">{q ? "Никого нет" : "Пока никого"}</p>
            ) : view === "people" ? (
              items.map((row) => {
                const active = person?.id === row.id && !composer;
                const sub = row.companies.map((c) => companyLine(c)).filter(Boolean).join(" · ");
                const meta = [pool === "all" ? row.owner_email : null, sub].filter(Boolean).join(" · ");
                return (
                  <button
                    key={row.id}
                    type="button"
                    onClick={() => {
                      setComposer(false);
                      setSelectedId(row.id);
                    }}
                    className={`flex w-full items-center gap-3 px-4 py-2.5 text-left ${
                      active ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-medium ${markTone(personTitle(row))}`}
                    >
                      {personMark(row)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[14px] leading-5">{personTitle(row)}</span>
                      {meta ? <span className="mt-0.5 block truncate text-[12px] text-muted">{meta}</span> : null}
                    </span>
                  </button>
                );
              })
            ) : (
              groups.map(({ org, people }) => {
                const key = org.org_key || org.label || "";
                const active = (group?.org.org_key || group?.org.label) === key && !composer;
                const inn = normalizeInn(org.inn);
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      setComposer(false);
                      setSelectedOrg(key);
                    }}
                    className={`flex w-full items-center gap-3 px-4 py-2.5 text-left ${
                      active ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"
                    }`}
                  >
                    <CompanyMark company={org.name} icon={org.company_icon} size={32} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[14px] leading-5">{companyLine(org)}</span>
                      <span className="mt-0.5 block truncate text-[12px] text-muted">
                        {inn ? `ИНН ${inn}` : ruCount(people.length, "человек", "человека", "человек")}
                      </span>
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        <section className="min-w-0 flex-1 overflow-y-auto px-10 py-6">
          {composer ? (
            <form
              className="mx-auto w-full max-w-[440px] pt-4"
              onSubmit={(e) => {
                e.preventDefault();
                void add();
              }}
            >
              <h2 className="text-[26px] font-semibold tracking-tight">Новый HR</h2>
              <p className="mt-2 text-[13px] leading-5 text-muted">
                Нужен Telegram, email или телефон. ИНН помогает не склеить разные компании с одним названием.
              </p>
              <div className="mt-8 space-y-6">
                <label className="block">
                  <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Человек</span>
                  <input
                    value={form.telegram_alias}
                    onChange={(e) => setForm((p) => ({ ...p, telegram_alias: e.target.value }))}
                    placeholder="@username"
                    autoComplete="off"
                    spellCheck={false}
                    autoFocus
                    className="!rounded-none !border-0 !border-b !border-line !bg-transparent !px-0 !py-2.5"
                  />
                  <div className="mt-3 grid grid-cols-2 gap-6">
                    <input
                      value={form.contact_email}
                      onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))}
                      placeholder="email"
                      autoComplete="off"
                      className="!rounded-none !border-0 !border-b !border-line !bg-transparent !px-0 !py-2.5"
                    />
                    <input
                      value={form.contact_phone}
                      onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))}
                      placeholder="телефон"
                      className="!rounded-none !border-0 !border-b !border-line !bg-transparent !px-0 !py-2.5"
                    />
                  </div>
                </label>
                <label className="block">
                  <span className="mb-2 block text-[11px] tracking-[0.16em] text-muted uppercase">Компания</span>
                  <input
                    value={form.company}
                    onChange={(e) => setForm((p) => ({ ...p, company: e.target.value }))}
                    placeholder="название или NDA"
                    className="!rounded-none !border-0 !border-b !border-line !bg-transparent !px-0 !py-2.5"
                  />
                  <input
                    value={form.company_inn}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, company_inn: e.target.value.replace(/\D/g, "").slice(0, 12) }))
                    }
                    placeholder="ИНН"
                    inputMode="numeric"
                    autoComplete="off"
                    className="mt-3 !rounded-none !border-0 !border-b !border-line !bg-transparent !px-0 !py-2.5"
                  />
                </label>
              </div>
              <button
                type="submit"
                disabled={busy || !canAdd}
                className="mt-8 text-[14px] text-accent disabled:opacity-40"
              >
                {busy ? "Сохраняю…" : "Сохранить"}
              </button>
            </form>
          ) : !loaded ? null : items.length === 0 ? (
            <div className="mx-auto max-w-[440px] pt-16">
              <p className="text-[22px] font-medium tracking-tight">{q ? "Никого не нашлось" : "Пока пусто"}</p>
              <p className="mt-3 text-[14px] leading-6 text-muted">
                {q
                  ? "Другой запрос или сбрось поиск."
                  : "Контакты с вакансий появляются сами. Своего HR добавь кнопкой сверху."}
              </p>
            </div>
          ) : view === "people" && person ? (
            <PersonDetail
              person={person}
              busy={busy}
              copied={copied}
              allPool={pool === "all"}
              onCopy={(value) => void copy(value)}
              onOpen={setOpenId}
              onRemove={(ids) => void removeSaved(ids)}
            />
          ) : view === "companies" && group ? (
            <div className="mx-auto w-full max-w-[440px] pt-6">
              <div className="flex items-start gap-4">
                <CompanyMark company={group.org.name} icon={group.org.company_icon} size={52} />
                <div className="min-w-0">
                  <p className="text-[11px] tracking-[0.16em] text-muted uppercase">Компания</p>
                  <h2 className="mt-2 text-[26px] font-semibold tracking-tight">{companyLine(group.org)}</h2>
                  {normalizeInn(group.org.inn) ? (
                    <p className="mt-2 text-[13px] tabular-nums text-muted">ИНН {normalizeInn(group.org.inn)}</p>
                  ) : isNdaName(group.org.name) ? (
                    <p className="mt-2 text-[13px] text-muted">без ИНН — не склеится с тёзками</p>
                  ) : null}
                </div>
              </div>
              <div className="mt-10 space-y-12">
                {group.people.map((row) => (
                  <PersonDetail
                    key={row.id}
                    person={row}
                    org={group.org}
                    compact
                    busy={busy}
                    copied={copied}
                    allPool={pool === "all"}
                    onCopy={(value) => void copy(value)}
                    onOpen={setOpenId}
                    onRemove={(ids) => void removeSaved(ids)}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </div>

      {openId != null && (
        <VacancyDrawer vacancyId={openId} initialPane="hr" onClose={() => setOpenId(null)} onChanged={() => void load()} />
      )}
    </div>
  );
}
