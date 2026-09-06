"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useHunt } from "@/components/hunt-context";
import { useWorkspace } from "@/components/workspace-context";

const SKIP = "hunt.skipOnboard.v1";

function skipKey(userId: number) {
  return `${SKIP}.${userId}`;
}

export function OnboardingSheet() {
  const { me } = useWorkspace();
  const { refresh } = useHunt();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!me) return;
    if (window.localStorage.getItem(skipKey(me.id))) return;
    api
      .onboardingStatus()
      .then((row) => setOpen(row.needed))
      .catch(() => setOpen(false));
  }, [me]);

  if (!open || !me) return null;

  function dismiss() {
    if (!me) return;
    window.localStorage.setItem(skipKey(me.id), "1");
    setOpen(false);
  }

  async function afterResume() {
    const seeded = await api.onboardingSeed();
    await refresh();
    if (seeded.seeded > 0) {
      setStatus(`Резюме на месте. В inbox уже ${seeded.seeded} карточки под твой стек.`);
      window.setTimeout(() => setOpen(false), 1200);
      return;
    }
    setStatus("Резюме сохранил. Карточек в общем пуле пока нет — вставь ссылку в inbox или включи поиск в настройках.");
    window.setTimeout(() => setOpen(false), 1800);
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadResume(file);
      await afterResume();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не прочитался файл");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-overlay px-4">
      <section className="w-full max-w-[420px] rounded-2xl border border-line bg-bg-soft p-6">
        <p className="text-[12px] text-muted">старт</p>
        <h2 className="mt-1 text-[22px] font-semibold tracking-tight">Положи резюме — появятся вакансии</h2>
        <p className="mt-2 text-[14px] leading-6 text-muted">
          PDF или текст. HuntOS разберёт резюме в ATS-поля и положит до трёх карточек в inbox, если такие вакансии уже есть в пуле.
        </p>
        {error && <p className="mt-3 text-[13px] text-rose-200">{error}</p>}
        {status && <p className="mt-3 text-[13px] text-accent">{status}</p>}
        <div className="mt-5 flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
            className="text-[14px] text-accent disabled:opacity-40"
          >
            {busy ? "Разбираю структуру…" : "загрузить PDF"}
          </button>
          <button type="button" onClick={dismiss} className="text-[13px] text-muted hover:text-ink">
            потом
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={(e) => void onFile(e.target.files?.[0])}
        />
      </section>
    </div>
  );
}
