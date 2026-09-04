"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/components/workspace-context";

type BotStatus = {
  available: boolean;
  username: string | null;
  connected: boolean;
  paused: boolean;
  telegram_username: string | null;
  want_vacancies: boolean;
  want_internships: boolean;
  want_hackathons: boolean;
  want_steps: boolean;
  want_ping: boolean;
};

const PREFS: { key: keyof BotStatus; label: string; hint: string }[] = [
  { key: "want_vacancies", label: "Новые вакансии", hint: "раз в сутки, только если появились" },
  { key: "want_internships", label: "Стажировки", hint: "когда набор открылся" },
  { key: "want_hackathons", label: "Хакатоны", hint: "новые живые события" },
  { key: "want_steps", label: "Собесы и скрининги", hint: "утром в день и за два часа" },
  { key: "want_ping", label: "Пинг HR", hint: "5 дней в «жду ответа», сразу @алиас" },
];

export function TelegramBotPanel() {
  const { me } = useWorkspace();
  const isHost = Boolean(me?.is_host);
  const [bot, setBot] = useState<BotStatus | null>(null);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await api.telegramBot();
    setBot(data);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, []);

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    await wrap(async () => {
      const { url } = await api.telegramBotLink();
      window.location.assign(url);
    });
  }

  const hint = bot?.connected
    ? `подключено${bot.telegram_username ? ` · @${bot.telegram_username}` : ""}${bot.paused ? " · пауза" : ""}`
    : bot?.available
      ? "откроется Telegram — сообщения только про твои вакансии"
      : isHost
        ? "вставь токен от @BotFather, потом люди смогут подключить уведомления"
        : "пока недоступно";

  return (
    <section className="mx-auto w-full max-w-[480px] pt-4">
      <h2 className="text-[26px] font-semibold tracking-tight">Уведомления</h2>
      {error && <p className="mt-4 text-sm text-rose-200">{error}</p>}
      {status && <p className="mt-4 text-sm text-accent">{status}</p>}

      <div className="mt-8 space-y-6">
        <p className={bot?.connected ? "text-[15px]" : "text-[14px] text-muted"}>{hint}</p>

        {isHost && (
          <div className="space-y-3">
            <input
              className="w-full"
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={bot?.available ? "токен сохранён — новый, чтобы заменить" : "токен от @BotFather"}
            />
            <button
              type="button"
              disabled={busy || !token.trim()}
              className="text-[14px] text-accent disabled:opacity-40"
              onClick={() =>
                void wrap(async () => {
                  await api.saveTelegramBotToken(token.trim());
                  setToken("");
                  await load();
                  setStatus("Токен сохранён");
                })
              }
            >
              Сохранить токен
            </button>
          </div>
        )}

        {bot?.connected && (
          <div className="space-y-3">
            {PREFS.map((item) => (
              <label key={item.key} className="flex items-start gap-3 text-[14px]">
                <input
                  type="checkbox"
                  checked={Boolean(bot[item.key])}
                  disabled={busy}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    void wrap(async () => {
                      const next = await api.saveTelegramBotPrefs({ [item.key]: checked });
                      setBot(next);
                    });
                  }}
                />
                <span>
                  {item.label}
                  <span className="mt-0.5 block text-[13px] text-muted">{item.hint}</span>
                </span>
              </label>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-5 text-[14px]">
          {bot?.connected ? (
            <button
              type="button"
              disabled={busy}
              className="text-muted hover:text-rose-200"
              onClick={() =>
                void wrap(async () => {
                  const next = await api.telegramBotUnlink();
                  setBot(next);
                  setStatus("Отключён");
                })
              }
            >
              Отключить
            </button>
          ) : (
            <button
              type="button"
              disabled={busy || !bot?.available}
              className="text-accent disabled:opacity-40"
              onClick={() => void connect()}
            >
              Подключить уведомления
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
