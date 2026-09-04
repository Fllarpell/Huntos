"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "@/lib/api";
import { FEEDBACK_PAGES, currentFeedbackPage } from "@/lib/feedback-pages";

type Kind = "bug" | "idea";

const COPY: Record<Kind, { title: string; hint: string; placeholder: string }> = {
  bug: {
    title: "Сообщить об ошибке",
    hint: "Что сломалось. Страницу и имя можно поправить ниже.",
    placeholder: "Например: в Inbox не открывается карточка после обновления…",
  },
  idea: {
    title: "Предложения и пожелания",
    hint: "Что добавить или поменять. Страницу и имя можно поправить ниже.",
    placeholder: "Например: хочу фильтр по зарплате на воронке…",
  },
};


export function FeedbackButtons() {
  const [kind, setKind] = useState<Kind | null>(null);

  return (
    <>
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setKind("bug")}
          className="block w-full text-left text-[13px] leading-5 text-muted hover:text-white"
        >
          Сообщить об ошибке
        </button>
        <button
          type="button"
          onClick={() => setKind("idea")}
          className="block w-full text-left text-[13px] leading-5 text-muted hover:text-white"
        >
          Предложения и пожелания
        </button>
      </div>
      {kind && <FeedbackSheet kind={kind} onClose={() => setKind(null)} />}
    </>
  );
}

function FeedbackSheet({ kind, onClose }: { kind: Kind; onClose: () => void }) {
  const copy = COPY[kind];
  const current = currentFeedbackPage();
  const [body, setBody] = useState("");
  const [page, setPage] = useState(current);
  const [contactName, setContactName] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageOptions = [
    { href: current, label: current },
    ...FEEDBACK_PAGES.filter((item) => item.label !== current).map((item) => ({
      href: item.label,
      label: item.label,
    })),
  ];

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.sendFeedback({
        kind,
        body,
        page: page.trim() || undefined,
        contact_name: contactName.trim() || undefined,
        reply_to: replyTo.trim() || undefined,
      });
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не отправилось");
    } finally {
      setBusy(false);
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-line bg-[#16181f] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.72)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="feedback-title"
      >
        <h2 id="feedback-title" className="text-[18px] font-semibold tracking-tight">
          {copy.title}
        </h2>
        {done ? (
          <p className="mt-4 text-[14px] text-accent">Отправлено</p>
        ) : (
          <>
            <p className="mt-2 text-[13px] text-muted">{copy.hint}</p>
            <textarea
              className="mt-4"
              rows={5}
              autoFocus
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={copy.placeholder}
            />
            <label className="mt-4 flex flex-col gap-1 text-[12px] text-muted">
              экран
              <select value={page} onChange={(e) => setPage(e.target.value)}>
                {pageOptions.map((item) => (
                  <option key={item.href} value={item.href}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-3 flex flex-col gap-1 text-[12px] text-muted">
              кто пишет
              <input
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                placeholder="имя, можно не заполнять"
              />
            </label>
            <label className="mt-3 flex flex-col gap-1 text-[12px] text-muted">
              как ответить
              <input
                value={replyTo}
                onChange={(e) => setReplyTo(e.target.value)}
                placeholder="@telegram или почта, можно не заполнять"
              />
            </label>
            {error && <p className="mt-3 text-sm text-rose-200">{error}</p>}
            <div className="mt-4 flex items-center justify-end gap-4">
              <button type="button" className="text-[14px] text-muted hover:text-white" onClick={onClose}>
                Закрыть
              </button>
              <button
                type="button"
                disabled={busy || body.trim().length < 8}
                className="text-[14px] text-accent disabled:opacity-40"
                onClick={() => void submit()}
              >
                {busy ? "…" : "Отправить"}
              </button>
            </div>
          </>
        )}
        {done && (
          <button type="button" className="mt-4 text-[14px] text-muted hover:text-white" onClick={onClose}>
            Закрыть
          </button>
        )}
      </div>
    </div>,
    document.body,
  );
}
