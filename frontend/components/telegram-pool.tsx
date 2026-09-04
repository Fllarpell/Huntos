"use client";

import { useEffect, useState } from "react";
import { api, type AuthUser, type TelegramPool } from "@/lib/api";
import { fromNow, relativeTime } from "@/lib/format";
import { GuideHint } from "@/components/guide";

export function TelegramPoolPanel({ user }: { user: AuthUser | null }) {
  const [pool, setPool] = useState<TelegramPool | null>(null);
  const [url, setUrl] = useState("");
  const [phone, setPhone] = useState("");
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await api.telegramPool();
    setPool(data);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка Telegram"));
  }, []);

  const host = pool?.host;
  const parsing = pool?.last_run?.status === "running";
  const isHost = Boolean(user?.is_host);

  useEffect(() => {
    if (!parsing) return;
    const timer = window.setInterval(() => {
      void load().catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [parsing]);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-[480px] pt-4">
      <div className="flex items-center gap-1.5">
        <h2 className="text-[26px] font-semibold tracking-tight">Telegram</h2>
        <GuideHint id="settings.telegram" />
      </div>
      {error && <p className="mt-4 text-sm text-rose-200">{error}</p>}
      {status && <p className="mt-4 text-sm text-accent">{status}</p>}

      <div className="mt-8 space-y-4">
        <p className="text-[11px] tracking-[0.16em] text-muted uppercase">Сессия</p>
        {host?.connected ? (
          <p className="text-sm">
            подключено{host.username ? ` · @${host.username}` : ""}
            {host.display_name ? ` · ${host.display_name}` : ""}
            {host.phone ? ` · ${host.phone}` : ""}
          </p>
        ) : (
          <p className="text-sm text-muted">
            {host?.waiting_code
              ? "код ушёл в Telegram — введи его ниже"
              : host?.needs_password
                ? "нужен облачный пароль 2FA"
                : "ещё не вошёл в Telegram"}
          </p>
        )}
        {host?.error && <p className="text-sm text-rose-200">{host.error}</p>}
        {pool?.last_run && (
          <p className="text-[13px] text-muted">
            последний прогон:{" "}
            {pool.last_run.status === "running"
              ? "идёт…"
              : pool.last_run.status === "ok"
                ? `готово · постов ${pool.last_run.found_count} · новых вакансий ${pool.last_run.new_count}`
                : pool.last_run.error || "ошибка"}
            {pool.last_run.finished_at ? ` · ${relativeTime(pool.last_run.finished_at)}` : ""}
          </p>
        )}

        {isHost && !host?.connected && (
          <div className="grid gap-3 sm:grid-cols-2">
            {!host?.waiting_code && !host?.needs_password && (
              <>
                <input
                  value={apiId}
                  onChange={(e) => setApiId(e.target.value)}
                  placeholder={host?.api_id_set ? "api_id сохранён" : "api_id с my.telegram.org"}
                />
                <input
                  type="password"
                  value={apiHash}
                  onChange={(e) => setApiHash(e.target.value)}
                  placeholder="api_hash"
                />
                <input
                    className="field-line"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+79001234567"
                />
                <button
                  disabled={busy}
                  onClick={() =>
                    void wrap(async () => {
                      await api.telegramHostStart({
                        phone,
                        api_id: apiId ? Number(apiId) : undefined,
                        api_hash: apiHash || undefined,
                      });
                      setStatus("Код отправлен в Telegram");
                    })
                  }
                  className="rounded-xl bg-accent/15 px-4 py-2 text-sm text-accent disabled:opacity-50"
                >
                  Прислать код
                </button>
              </>
            )}
            {(host?.waiting_code || host?.needs_password) && (
              <>
                {host.waiting_code && (
                  <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="код из Telegram" />
                )}
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={host.needs_password ? "облачный пароль 2FA" : "2FA, если спросит"}
                />
                <button
                  disabled={busy}
                  onClick={() =>
                    void wrap(async () => {
                      const next = await api.telegramHostConfirm({ code, password: password || undefined });
                      if (next.needs_password) setStatus("Нужен облачный пароль");
                      else setStatus("Telegram подключён");
                      setCode("");
                      setPassword("");
                    })
                  }
                  className="rounded-xl bg-accent/15 px-4 py-2 text-sm text-accent disabled:opacity-50"
                >
                  Подтвердить
                </button>
              </>
            )}
          </div>
        )}
        {isHost && host?.connected && (
          <button
            disabled={busy}
            onClick={() =>
              void wrap(async () => {
                await api.telegramHostDisconnect();
                setStatus("Отключён");
              })
            }
            className="rounded-xl px-4 py-2 text-sm text-muted hover:text-rose-200"
          >
            Отключить
          </button>
        )}
      </div>

      <div className="flex gap-2">
        <input
          className="field-line flex-1"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="@pythonjobs или https://t.me/channel"
        />
        <button
          disabled={busy || !url.trim()}
          onClick={() =>
            void wrap(async () => {
              await api.addTelegramChannel(url.trim());
              setUrl("");
              setStatus("Канал в списке");
            })
          }
          className="text-[14px] text-accent disabled:opacity-50"
        >
          Добавить
        </button>
      </div>

      <button
        disabled={busy || parsing || !host?.connected}
        onClick={() =>
          void wrap(async () => {
            await api.parseTelegram();
            setStatus("Парсер каналов пошёл");
          })
        }
        className="rounded-xl bg-accent/15 px-4 py-2 text-sm text-accent disabled:opacity-50"
      >
        {parsing ? "Читает каналы…" : "Прочитать каналы сейчас"}
      </button>

      <div className="space-y-2">
        {(pool?.channels ?? []).length === 0 && <p className="text-sm text-muted">Пока нет каналов — добавь @channel выше</p>}
        {(pool?.channels ?? []).map((c) => (
          <div key={c.id} className="flex items-start justify-between gap-3 border-b border-white/[0.06] py-3 last:border-0">
            <div className="min-w-0">
              <p className="truncate font-medium">{c.title || c.username}</p>
              <p className="text-[13px] text-muted">
                @{c.username.replace(/^\+/, "")}
                {c.joined ? " · подписан" : " · в очереди"}
                {c.last_parsed_at ? ` · ${fromNow(c.last_parsed_at)}` : ""}
              </p>
              {c.error && <p className="text-[13px] text-rose-200">{c.error}</p>}
            </div>
            {(isHost || c.added_by_user_id === user?.id) && (
              <button
                onClick={() =>
                  void wrap(async () => {
                    await api.deleteTelegramChannel(c.id);
                  })
                }
                className="shrink-0 rounded-xl px-3 py-2 text-sm text-muted hover:text-rose-200"
              >
                Убрать
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
