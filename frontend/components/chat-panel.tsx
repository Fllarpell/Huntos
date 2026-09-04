"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { api, type ChatMessage, type ChatThread } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { GuideHint, GuideSpot } from "@/components/guide";
import { useWorkspace } from "@/components/workspace-context";

function seenLabel(online: boolean, lastSeen: string | null) {
  if (online) return "онлайн";
  const rel = relativeTime(lastSeen);
  if (!rel) return "давно не заходил";
  if (rel === "только что") return "был только что";
  return `был ${rel}`;
}

function initials(name: string) {
  const parts = name.trim().split(/[\s@._-]+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}

function PeerMark({ name, online }: { name: string; online: boolean }) {
  return (
    <span className="relative shrink-0">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.07] text-[11px] font-medium tracking-wide text-white/85">
        {initials(name)}
      </span>
      <span
        className={`absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#12141b] ${
          online ? "bg-emerald-400" : "bg-white/25"
        }`}
      />
    </span>
  );
}

export function ChatEntry() {
  const { me } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  if (!me) return null;

  return (
    <>
      <GuideSpot id="shell.chat">
        <span className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="block w-full text-left text-[13px] leading-5 text-muted hover:text-white"
          >
            Диалоги
            {unread > 0 ? <span className="ml-1 text-accent">· {unread}</span> : null}
          </button>
          <GuideHint id="shell.chat" />
        </span>
      </GuideSpot>
      {open ? (
        <ChatSheet host={Boolean(me.is_host)} onClose={() => setOpen(false)} onUnread={setUnread} />
      ) : (
        <ChatBadgePoll onUnread={setUnread} />
      )}
    </>
  );
}

function ChatBadgePoll({ onUnread }: { onUnread: (n: number) => void }) {
  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const data = await api.chatInbox();
        if (!stop) onUnread(data.unread_total);
      } catch {
        /* ignore */
      }
    }
    void tick();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void tick();
    }, 12000);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [onUnread]);
  return null;
}

function ChatSheet({
  host,
  onClose,
  onUnread,
}: {
  host: boolean;
  onClose: () => void;
  onUnread: (n: number) => void;
}) {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadInbox = useCallback(async () => {
    const data = await api.chatInbox();
    setThreads(data.threads);
    onUnread(data.unread_total);
    setActiveId((cur) => {
      if (cur != null && data.threads.some((row) => row.id === cur)) return cur;
      return data.threads[0]?.id ?? null;
    });
    setError(null);
    return data;
  }, [onUnread]);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        if (!stop) await loadInbox();
      } catch (e) {
        if (!stop) setError(e instanceof Error ? e.message : "Не загрузилось");
      }
    }
    void tick();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void tick();
    }, 4000);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [loadInbox]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const active = threads.find((row) => row.id === activeId) ?? null;
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return threads;
    return threads.filter(
      (row) =>
        row.peer_name.toLowerCase().includes(needle) || (row.last_body || "").toLowerCase().includes(needle),
    );
  }, [threads, q]);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 px-4 backdrop-blur-[2px]" onClick={onClose}>
      <div
        className="flex h-[min(78vh,640px)] w-full max-w-[760px] overflow-hidden rounded-2xl border border-white/[0.08] bg-[#101218] shadow-[0_28px_90px_rgba(0,0,0,0.78)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-title"
      >
        <aside className="flex w-[248px] shrink-0 flex-col border-r border-white/[0.06] bg-[#0c0e13]">
          <div className="border-b border-white/[0.06] px-4 py-3.5">
            <h2 id="chat-title" className="text-[15px] font-semibold tracking-tight">
              Диалоги
            </h2>
            <p className="mt-0.5 text-[12px] text-muted">{host ? "люди на HuntOS" : "связь с админом"}</p>
            {host && threads.length > 6 ? (
              <input
                className="mt-2.5 !rounded-lg !border-white/10 !bg-white/[0.04] !py-1.5 text-[13px]"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="найти"
              />
            ) : null}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-1">
            {filtered.length === 0 && !error ? (
              <p className="px-4 py-6 text-[13px] text-muted">Пока пусто</p>
            ) : null}
            {filtered.map((row) => {
              const on = row.id === activeId;
              return (
                <button
                  key={row.id}
                  type="button"
                  onClick={() => setActiveId(row.id)}
                  className={`flex w-full items-center gap-3 px-3.5 py-2.5 text-left transition ${
                    on ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"
                  }`}
                >
                  <PeerMark name={row.peer_name} online={row.online} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className={`truncate text-[13px] ${on ? "text-white" : "text-white/90"}`}>
                        {row.peer_name}
                      </span>
                      {row.unread > 0 ? (
                        <span className="rounded-full bg-accent/20 px-1.5 py-0.5 text-[10px] tabular-nums text-accent">
                          {row.unread}
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block truncate text-[12px] text-muted">
                      {row.last_body || seenLabel(row.online, row.last_seen_at)}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col bg-[#12141b]">
          <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3">
            {active ? <PeerMark name={active.peer_name} online={active.online} /> : null}
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-semibold tracking-tight">
                {active?.peer_name || "Диалог"}
              </p>
              <p className={`text-[12px] ${active?.online ? "text-emerald-300/90" : "text-muted"}`}>
                {active ? seenLabel(active.online, active.last_seen_at) : "выбери диалог слева"}
              </p>
            </div>
            <button
              type="button"
              aria-label="Закрыть"
              className="rounded-lg p-1.5 text-muted hover:bg-white/[0.05] hover:text-white"
              onClick={onClose}
            >
              <X size={16} strokeWidth={1.75} />
            </button>
          </div>
          {error ? <p className="px-4 pt-3 text-sm text-rose-200">{error}</p> : null}
          {active ? (
            <ThreadView
              key={active.id}
              thread={active}
              onSent={() => {
                void loadInbox();
              }}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center px-6">
              <p className="text-[14px] text-muted">
                {error ? "Диалог не открылся. Закрой и попробуй ещё раз." : "Выбери диалог слева."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function ThreadView({ thread, onSent }: { thread: ChatThread; onSent: () => void }) {
  const [items, setItems] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const lastId = items.at(-1)?.id ?? 0;

  const load = useCallback(
    async (after = 0) => {
      const rows = await api.chatMessages(thread.id, after);
      if (after <= 0) setItems(rows);
      else if (rows.length) {
        setItems((prev) => {
          const seen = new Set(prev.map((item) => item.id));
          return [...prev, ...rows.filter((row) => !seen.has(row.id))];
        });
      }
    },
    [thread.id],
  );

  useEffect(() => {
    let stop = false;
    void load(0).catch((e) => {
      if (!stop) setError(e instanceof Error ? e.message : "Не загрузилось");
    });
    return () => {
      stop = true;
    };
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void load(lastId).catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(id);
  }, [load, lastId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [items.length, lastId]);

  async function send() {
    const body = draft.trim();
    if (body.length < 1 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const row = await api.chatSend(thread.id, body);
      setItems((prev) => (prev.some((item) => item.id === row.id) ? prev : [...prev, row]));
      setDraft("");
      onSent();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не отправилось");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-4 py-4">
        {items.length === 0 ? (
          <p className="pt-8 text-center text-[13px] text-muted">Напиши первое сообщение.</p>
        ) : (
          items.map((row) => (
            <div key={row.id} className={`flex ${row.mine ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[78%] px-3.5 py-2 text-[14px] leading-5 ${
                  row.mine
                    ? "rounded-[18px] rounded-br-md bg-accent/18 text-white"
                    : "rounded-[18px] rounded-bl-md bg-white/[0.06] text-white/90"
                }`}
              >
                <p className="whitespace-pre-wrap">{row.body}</p>
                <p className={`mt-1 text-[11px] ${row.mine ? "text-right text-white/45" : "text-muted"}`}>
                  {relativeTime(row.created_at)}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={bottom} />
      </div>
      {error ? <p className="px-4 pb-1 text-sm text-rose-200">{error}</p> : null}
      <form
        className="border-t border-white/[0.06] bg-[#0e1015] px-3 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <div className="flex items-end gap-2 rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-2 focus-within:border-accent/40">
          <textarea
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder="сообщение"
            className="!min-h-[28px] max-h-28 flex-1 resize-none !border-0 !bg-transparent !p-0 !shadow-none focus:!border-transparent focus:!shadow-none"
          />
          <button
            type="submit"
            disabled={busy || draft.trim().length < 1}
            className="shrink-0 pb-0.5 text-[13px] font-medium text-accent disabled:opacity-35"
          >
            {busy ? "…" : "Отправить"}
          </button>
        </div>
      </form>
    </>
  );
}
