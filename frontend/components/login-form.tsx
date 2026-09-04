"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { setPendingFirstTour } from "@/lib/guide";

const GOOGLE_MESSAGES: Record<string, string> = {
  "no-refresh": "Google не отдал доступ. Нажми ещё раз.",
  "oauth-mismatch": "Сессия прервалась. Нажми ещё раз.",
  "oauth-state": "Сессия сломалась. Нажми ещё раз.",
  "no-user": "Не нашли аккаунт.",
  "email-taken": "Этот email уже с паролем. Войди им, Google сам не привяжется.",
  "unverified-email": "Google не подтвердил почту.",
  access_denied: "Доступ не выдан.",
};

export function LoginForm() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [googleOn, setGoogleOn] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("google");
    if (raw) {
      setError(GOOGLE_MESSAGES[raw] || "Не вышло войти через Google");
      window.history.replaceState({}, "", "/login");
    }
    api
      .me()
      .then(() => {
        window.location.href = "/";
      })
      .catch(() => {
        /* stay on login */
      });
    api
      .googleAvailable()
      .then((row) => setGoogleOn(row.available))
      .catch(() => setGoogleOn(false));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        const user = await api.register(email, password);
        setPendingFirstTour(user.id);
      } else {
        await api.login(email, password);
      }
      window.location.href = "/";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не вышло");
    } finally {
      setBusy(false);
    }
  }

  async function onGoogle() {
    setBusy(true);
    setError(null);
    try {
      const { url } = await api.googleLogin();
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google вход пока недоступен");
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-16">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-[46%] h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/[0.08] blur-[110px]" />
      </div>

      <div className="relative w-full max-w-[380px]">
        <div className="mb-7 px-1">
          <p className="text-[12px] tracking-[0.2em] text-muted uppercase">Job CRM</p>
          <h1 className="mt-1.5 text-[28px] font-semibold tracking-tight">HuntOS</h1>
        </div>

        <div className="rounded-2xl border border-line bg-card p-6">
          {error && <p className="mb-5 rounded-xl bg-rose-400/10 px-3.5 py-2.5 text-sm text-rose-100">{error}</p>}

          {googleOn && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void onGoogle()}
              className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-white/[0.07] px-4 py-3 text-[14px] text-white hover:bg-white/[0.1] disabled:opacity-50"
            >
              <GoogleMark />
              Продолжить с Google
            </button>
          )}

          {googleOn && (
            <div className="my-5 flex items-center gap-3">
              <span className="h-px flex-1 bg-line" />
              <span className="text-[12px] text-muted">или почтой</span>
              <span className="h-px flex-1 bg-line" />
            </div>
          )}

          <form onSubmit={(e) => void onSubmit(e)} className="space-y-4" autoComplete="off">
            <div className="grid grid-cols-2 rounded-xl bg-white/[0.04] p-1">
              <button
                type="button"
                onClick={() => setMode("login")}
                className={`rounded-lg py-2 text-[13px] outline-none ${
                  mode === "login" ? "bg-white/[0.09] text-white" : "text-muted hover:text-white"
                }`}
              >
                Войти
              </button>
              <button
                type="button"
                onClick={() => setMode("register")}
                className={`rounded-lg py-2 text-[13px] outline-none ${
                  mode === "register" ? "bg-white/[0.09] text-white" : "text-muted hover:text-white"
                }`}
              >
                Регистрация
              </button>
            </div>
            <label className="block space-y-1.5">
              <span className="text-[12px] text-muted">Почта</span>
              <input
                type="text"
                autoComplete="off"
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                data-1p-ignore="true"
                data-lpignore="true"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                name="hunt-email"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-[12px] text-muted">Пароль</span>
              <input
                type="text"
                className="password-mask"
                autoComplete="off"
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                data-1p-ignore="true"
                data-lpignore="true"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="минимум 8 символов"
                name="hunt-secret"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl bg-accent py-3 text-[14px] font-medium text-[#0b0c0e] hover:bg-[#8fe0d4] disabled:opacity-50"
            >
              {busy ? "…" : mode === "register" ? "Создать аккаунт" : "Войти"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3.1l5.7-5.7C34.2 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 12 24 12c3.1 0 5.8 1.2 8 3.1l5.7-5.7C34.2 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.3C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.6 39.6 16.3 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-1.1 3.2-3.5 5.7-6.7 7.2l6.3 5.3C38.2 37.3 44 32 44 24c0-1.2-.1-2.3-.4-3.5z" />
    </svg>
  );
}
