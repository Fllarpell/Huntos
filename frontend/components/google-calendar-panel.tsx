"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

const GOOGLE_MESSAGES: Record<string, string> = {
  ok: "Календарь Hunt подключён. Собесы и дедлайны идут туда, не в основной Google",
  "no-refresh": "Google не отдал refresh-токен. Нажми «Подключить» ещё раз и разреши доступ.",
  "oauth-mismatch": "Сессия Google прервалась. Нажми «Подключить» ещё раз.",
  "oauth-state": "Сессия Google сломалась. Нажми «Подключить» ещё раз.",
  "no-user": "Не нашли аккаунт Hunt для этого Google.",
  access_denied: "Доступ к календарю не выдан.",
};

export function GoogleCalendarPanel() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api.ownProfile().then(setProfile).catch(() => undefined);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("google");
    if (!raw) return;
    const mapped = GOOGLE_MESSAGES[raw];
    if (raw === "ok") setStatus(mapped);
    else setError(mapped || `Google: ${decodeURIComponent(raw)}`);
    window.history.replaceState({}, "", "/settings");
  }, []);

  const redirectUri = profile?.google_redirect_uri || "http://localhost:3000/api/google/callback";

  async function wrap(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка Google");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-[480px] pt-4">
      <h2 className="text-[26px] font-semibold tracking-tight">Календарь</h2>
      <p className="mt-2 text-[13px] leading-5 text-muted">
        Собесы, скрины и дедлайны пишутся в отдельный календарь Hunt. Личные встречи в Google не трогаем.
      </p>
      {error && <p className="mt-4 text-sm text-rose-200">{error}</p>}
      {status && <p className="mt-4 text-sm text-accent">{status}</p>}

      <div className="mt-8 space-y-5">
        {profile?.google_connected ? (
          <p className="text-[15px]">
            подключено{profile.google_email ? ` · ${profile.google_email}` : ""}
            {profile.google_calendar_ready ? " · Hunt" : ""}
          </p>
        ) : (
          <p className="text-[14px] text-muted">
            {profile?.google_client_id_set
              ? "ключи сохранены — нажми «Подключить Google»"
              : "нужны Client ID и Secret из Google Cloud"}
          </p>
        )}
        {profile?.google_needs_reconnect && (
          <p className="text-[13px] leading-5 text-amber-200">
            Google вошёл, но календарь Hunt ещё не создан. Обычно в Google Cloud не включён Calendar API.
          </p>
        )}
        {profile?.google_calendar_error && (
          <p className="text-[13px] text-rose-200">{profile.google_calendar_error}</p>
        )}

        <div>
          <p className="text-[11px] tracking-[0.16em] text-muted uppercase">Redirect URI</p>
          <button
            type="button"
            className="mt-2 break-all text-left text-[13px] text-accent"
            onClick={() => void navigator.clipboard.writeText(redirectUri).then(() => setStatus("URI скопирован"))}
          >
            {redirectUri}
          </button>
        </div>
        <p className="text-[13px] leading-5 text-muted">
          В Google Cloud создай OAuth Web client, включи Calendar API и вставь ключи ниже. Если приложение в режиме Testing — добавь свой Gmail в Test users.
        </p>

        <input
          className="field-line"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder={profile?.google_client_id_set ? "Client ID сохранён — новый, чтобы заменить" : "Client ID"}
        />
        <input
          className="field-line"
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          placeholder={profile?.google_client_id_set ? "Secret сохранён — новый, чтобы заменить" : "Client Secret"}
        />
        <div className="flex flex-wrap gap-5 pt-2 text-[14px]">
          <button
            disabled={busy || (!clientId.trim() && !clientSecret.trim())}
            className="text-muted hover:text-white disabled:opacity-40"
            onClick={() =>
              void wrap(async () => {
                const saved = await api.saveProfile(
                  {
                    ...(clientId.trim() ? { google_client_id: clientId.trim() } : {}),
                    ...(clientSecret.trim() ? { google_client_secret: clientSecret.trim() } : {}),
                  },
                  { asUser: false },
                );
                setProfile(saved);
                setClientId("");
                setClientSecret("");
                setStatus("Ключи Google сохранены");
              })
            }
          >
            Сохранить ключи
          </button>
          {profile?.google_connected ? (
            <>
              {profile.google_needs_reconnect && (
                <>
                  <button
                    disabled={busy}
                    className="text-accent"
                    onClick={() =>
                      void wrap(async () => {
                        await api.googleCalendar();
                        const fresh = await api.ownProfile();
                        setProfile(fresh);
                        setStatus("Календарь Hunt создан");
                      })
                    }
                  >
                    Создать календарь Hunt
                  </button>
                  <button
                    disabled={busy}
                    className="text-muted hover:text-white"
                    onClick={() =>
                      void wrap(async () => {
                        const { url } = await api.googleConnect();
                        window.location.href = url;
                      })
                    }
                  >
                    Подключить ещё раз
                  </button>
                </>
              )}
              <button
                disabled={busy}
                className="text-muted hover:text-rose-200"
                onClick={() =>
                  void wrap(async () => {
                    await api.googleDisconnect();
                    const fresh = await api.ownProfile();
                    setProfile(fresh);
                    setStatus("Google отключён. Календарь Hunt в Google остаётся.");
                  })
                }
              >
                Отключить
              </button>
            </>
          ) : (
            <button
              disabled={busy}
              className="text-accent"
              onClick={() =>
                void wrap(async () => {
                  const { url } = await api.googleConnect();
                  window.location.href = url;
                })
              }
            >
              Подключить Google
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
