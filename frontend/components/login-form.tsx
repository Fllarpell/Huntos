"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

export function LoginForm() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .me()
      .then(() => {
        window.location.href = "/";
      })
      .catch(() => {
        /* stay on login */
      });
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        await api.register(email, password);
      } else {
        await api.login(email, password);
      }
      await api.me();
      window.location.href = "/";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не вышло");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <form
        onSubmit={(e) => void onSubmit(e)}
        className="w-full max-w-sm space-y-6"
        autoComplete="off"
      >
        <div>
          <p className="text-[13px] tracking-[0.18em] text-muted uppercase">Job CRM</p>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Hunt</h1>
          <p className="mt-2 text-sm leading-5 text-muted">
            Свой вход — своя воронка. Другие люди на этом сервере твои вакансии не увидят.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`rounded-full px-3 py-1.5 text-[13px] ${
              mode === "login" ? "bg-accent/18 text-accent" : "bg-white/5 text-muted"
            }`}
          >
            Войти
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`rounded-full px-3 py-1.5 text-[13px] ${
              mode === "register" ? "bg-accent/18 text-accent" : "bg-white/5 text-muted"
            }`}
          >
            Регистрация
          </button>
        </div>
        {error && <p className="rounded-xl bg-rose-400/10 px-4 py-3 text-sm text-rose-100">{error}</p>}
        <label className="block space-y-2">
          <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Email</span>
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
        <label className="block space-y-2">
          <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Пароль</span>
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
          className="w-full rounded-xl bg-accent/20 px-4 py-2.5 text-sm text-accent disabled:opacity-50"
        >
          {busy ? "…" : mode === "register" ? "Создать аккаунт" : "Войти"}
        </button>
        {mode === "register" && (
          <p className="text-[12px] leading-5 text-muted">
            Первый аккаунт на сервере получит уже найденные вакансии. Следующие получают копии из общих каналов, воронка у каждого своя.
          </p>
        )}
      </form>
    </div>
  );
}
