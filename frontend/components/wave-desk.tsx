"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Thesis, Vacancy, WavePack } from "@/lib/types";
import { MatchBadge } from "./match-badge";
import { CompanyMark } from "./company-mark";
import { TelegramChatLink } from "./telegram-chat-link";
import { telegramHandle, vacancyTelegramUrl } from "@/lib/format";

export function WaveDesk({
  thesis,
  onClose,
  onSent,
  onOpen,
}: {
  thesis: Thesis;
  onClose: () => void;
  onSent: () => void;
  onOpen?: (id: number) => void;
}) {
  const [pack, setPack] = useState<WavePack | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [items, setItems] = useState<Vacancy[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function load() {
    const data = await api.wavePack(thesis.id);
    setPack(data);
    setItems(data.items);
    setChecked(new Set(data.suggested_ids));
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Не собралась пачка"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thesis.id]);

  const selected = useMemo(() => items.filter((v) => checked.has(v.id)), [items, checked]);
  const needDraft = selected.filter((v) => !v.telegram_message);
  const packMax = pack?.pack_max ?? 50;

  function toggle(id: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size >= packMax) return prev;
      else next.add(id);
      return next;
    });
  }

  async function draftSelected() {
    setError(null);
    const queue = needDraft.slice(0, packMax);
    if (!queue.length) {
      setStatus("Черновики уже есть");
      return;
    }
    let done = 0;
    for (const vacancy of queue) {
      setBusy(`draft-${vacancy.id}`);
      setStatus(`Черновик ${done + 1} из ${queue.length}`);
      try {
        const { telegram_message } = await api.telegramDraft(vacancy.id);
        setItems((prev) => prev.map((item) => (item.id === vacancy.id ? { ...item, telegram_message } : item)));
        done += 1;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Черновик не собрался");
        break;
      }
    }
    setBusy(null);
    if (done) setStatus(`Готово черновиков: ${done}`);
  }

  async function wroteSelected() {
    setError(null);
    const ids = selected.map((v) => v.id).slice(0, packMax);
    if (!ids.length) {
      setError("Выбери карточки");
      return;
    }
    setBusy("wrote");
    try {
      const result = await api.waveWrote(thesis.id, ids);
      setStatus(`Написал ${result.wrote}. Карточки в «жду ответа».`);
      await load();
      onSent();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не отметилось");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-2xl border border-accent/25 bg-accent/5 p-5 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[12px] tracking-[0.14em] text-accent uppercase">Волна</p>
          <h2 className="mt-1 text-[18px] font-medium">{thesis.name}</h2>
          <p className="mt-1 text-sm leading-5 text-muted">
            Пачка из Inbox. Скопируй черновик и напиши в Telegram сам — Hunt письмо не отправит. «Написал» сдвинет карточки в «жду ответа». В одной волне до {packMax}.
          </p>
        </div>
        <button type="button" className="text-sm text-muted hover:text-white" onClick={onClose}>
          Закрыть
        </button>
      </div>
      {error && <p className="rounded-xl bg-rose-400/10 px-3 py-2 text-sm text-rose-100">{error}</p>}
      {status && <p className="text-sm text-accent">{status}</p>}
      {!pack ? (
        <p className="text-sm text-muted">Собираю inbox…</p>
      ) : pack.inbox_total === 0 ? (
        <p className="text-sm text-muted">В Inbox нет вакансий под этот тезис.</p>
      ) : (
        <>
          <p className="text-sm text-muted">
            в inbox {pack.inbox_total} · в пачке {selected.length} из {packMax}
            {pack.items.length < pack.inbox_total ? ` · на экране ${pack.items.length}` : ""}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={Boolean(busy) || !needDraft.length}
              className="rounded-xl bg-accent/20 px-4 py-2 text-sm text-accent disabled:opacity-40"
              onClick={() => void draftSelected()}
            >
              {busy?.startsWith("draft") ? status : `Черновики TG · ${needDraft.length}`}
            </button>
            <button
              type="button"
              disabled={Boolean(busy) || !selected.length}
              className="rounded-xl bg-white/8 px-4 py-2 text-sm disabled:opacity-40"
              onClick={() => void wroteSelected()}
            >
              {busy === "wrote" ? "Отмечаю…" : `Написал выбранные · ${selected.length}`}
            </button>
          </div>
          <div className="divide-y divide-white/6 rounded-2xl border border-line bg-card/40">
            {items.map((v) => {
              const chat = vacancyTelegramUrl(v);
              const on = checked.has(v.id);
              const expanded = openId === v.id;
              return (
                <article key={v.id} className={`px-3 py-3 ${on ? "bg-accent/6" : ""}`}>
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(v.id)}
                      className="mt-1 h-4 w-4 accent-teal-300"
                    />
                    <CompanyMark vacancy={v} size={28} />
                    <div className="min-w-0 flex-1">
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() => (onOpen ? onOpen(v.id) : undefined)}
                        >
                          <div className="flex items-center gap-2">
                            <p className="truncate text-[15px] font-medium">{v.company || "без компании"}</p>
                            <MatchBadge score={v.match_score} status={v.scoring_status} size="sm" />
                          </div>
                          <p className="truncate text-[13px] text-white/80">{v.title}</p>
                        </button>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px]">
                        {chat ? (
                          <TelegramChatLink href={chat} />
                        ) : (
                          <span className="text-muted">нет @hr</span>
                        )}
                        {telegramHandle(v.telegram_alias) && (
                          <span className="text-muted">{telegramHandle(v.telegram_alias)}</span>
                        )}
                        {v.telegram_message ? (
                          <span className="text-accent">черновик есть</span>
                        ) : (
                          <span className="text-muted">нет черновика</span>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col gap-1">
                      {v.telegram_message && (
                        <button
                          type="button"
                          className="rounded-lg bg-white/8 px-2 py-1 text-[11px]"
                          onClick={() => void navigator.clipboard.writeText(v.telegram_message || "")}
                        >
                          Копировать
                        </button>
                      )}
                      {v.telegram_message && (
                        <button
                          type="button"
                          className="rounded-lg px-2 py-1 text-[11px] text-muted hover:text-white"
                          onClick={() => setOpenId(expanded ? null : v.id)}
                        >
                          {expanded ? "скрыть" : "текст"}
                        </button>
                      )}
                    </div>
                  </div>
                  {expanded && v.telegram_message && (
                    <pre className="mt-3 whitespace-pre-wrap rounded-xl bg-black/20 px-3 py-2 font-sans text-[13px] leading-6 text-white/85">
                      {v.telegram_message}
                    </pre>
                  )}
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
