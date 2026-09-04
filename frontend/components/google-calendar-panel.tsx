"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { GuideHint } from "@/components/guide";
import { useWorkspace } from "@/components/workspace-context";

const GOOGLE_MESSAGES: Record<string, string> = {
  ok: "Календарь подключён",
  "no-refresh": "Google не отдал refresh-токен. Нажми «Подключить» ещё раз.",
  "oauth-mismatch": "Сессия прервалась. Нажми «Подключить» ещё раз.",
  "oauth-state": "Сессия сломалась. Нажми «Подключить» ещё раз.",
  "no-user": "Не нашли аккаунт.",
  access_denied: "Доступ не выдан.",
};

export function GoogleCalendarPanel() {
  const { me } = useWorkspace();
  const isHost = Boolean(me?.is_host);
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
  const canConnect = Boolean(profile?.google_client_id_set);

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
      <div className="flex items-center gap-1.5">
        <h2 className="text-[26px] font-semibold tracking-tight">Календарь</h2>
        <GuideHint id="settings.calendar" />
      </div>
      {error && <p className="mt-4 text-sm text-rose-200">{error}</p>}
      {status && <p className="mt-4 text-sm text-accent">{status}</p>}

      <div className="mt-8 space-y-5">
        {profile?.google_connected ? (
          <p className="text-[15px]">
            подключено{profile.google_email ? ` · ${profile.google_email}` : ""}
            {profile.google_calendar_ready ? " · HuntOS" : ""}
          </p>
        ) : (
          <p className="text-[14px] text-muted">
            {canConnect ? "можно подключить Google" : "Google пока недоступен"}
          </p>
        )}
        {profile?.google_needs_reconnect && (
          <p className="text-[13px] leading-5 text-amber-200">Календарь HuntOS ещё не создан.</p>
        )}
        {profile?.google_calendar_error && (
          <p className="text-[13px] text-rose-200">{profile.google_calendar_error}</p>
        )}

        {isHost && (
          <>
            <div>
              <p className="mt-2 text-[12px] leading-4 text-muted">этот URI — в Google Cloud → Authorized redirect URIs</p>
              <button
                type="button"
                className="mt-2 break-all text-left text-[13px] text-accent"
                onClick={() => void navigator.clipboard.writeText(redirectUri).then(() => setStatus("URI скопирован"))}
              >
                {redirectUri}
              </button>
            </div>

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
          </>
        )}
        <div className="flex flex-wrap gap-5 pt-2 text-[14px]">
          {isHost && (
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
          )}
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
                        setStatus("Календарь HuntOS создан");
                      })
                    }
                  >
                    Создать календарь HuntOS
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
                    setStatus("Отключён");
                  })
                }
              >
                Отключить
              </button>
            </>
          ) : (
            <button
              disabled={busy || !canConnect}
              className="text-accent disabled:opacity-40"
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
