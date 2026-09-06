"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CustomFieldDef, Profile } from "@/lib/types";
import { TelegramPoolPanel } from "@/components/telegram-pool";
import { GoogleCalendarPanel } from "@/components/google-calendar-panel";
import { HuntFieldsEditor } from "@/components/hunt-fields-editor";
import { GuideHint, GuideSpot } from "@/components/guide";
import { SearchesSettings } from "@/components/searches-settings";
import { useHunt } from "@/components/hunt-context";
import { useWorkspace } from "@/components/workspace-context";
import { FeedbackInbox } from "@/components/feedback-inbox";
import { setFeedbackSettingsTab } from "@/lib/feedback-pages";
import { TelegramBotPanel } from "@/components/telegram-bot-panel";
import { PageHead } from "./page-head";

export function SettingsPanel() {
  const { hunts, activeHuntId, refresh: refreshHunts } = useHunt();
  const { me, users, asUserId, refreshUsers } = useWorkspace();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [resume, setResume] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<
    "profile" | "fields" | "calendar" | "notify" | "telegram" | "searches" | "messages" | "people"
  >("profile");
  const [fields, setFields] = useState<CustomFieldDef[]>([]);
  const [fieldsHuntId, setFieldsHuntId] = useState<number | null>(null);
  const [busyUser, setBusyUser] = useState<number | null>(null);

  async function load() {
    const p = await api.profile();
    setProfile(p);
    setResume(p.resume_text ?? "");
    setFields(p.custom_fields || []);
  }

  useEffect(() => {
    if (!fieldsHuntId) {
      const next = activeHuntId ?? hunts[0]?.id ?? null;
      if (next) setFieldsHuntId(next);
      return;
    }
    const hunt = hunts.find((item) => item.id === fieldsHuntId);
    if (hunt) setFields(hunt.custom_fields || []);
  }, [hunts, fieldsHuntId, activeHuntId]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [asUserId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") && me?.is_host) setTab("calendar");
    if (params.get("tab") === "fields") setTab("fields");
  }, [me]);

  useEffect(() => {
    if (!me?.is_host && (tab === "calendar" || tab === "telegram" || tab === "messages" || tab === "people")) {
      setTab("profile");
    }
  }, [me, tab]);

  useEffect(() => {
    const labels: Record<string, string> = {
      profile: "Профиль",
      fields: "Поля карточки",
      searches: "Поиски",
      notify: "Уведомления",
      calendar: "Календарь",
      telegram: "Telegram",
      people: "Люди",
      messages: "Сообщения",
    };
    setFeedbackSettingsTab(labels[tab] ?? "Настройки");
    return () => setFeedbackSettingsTab(null);
  }, [tab]);

  async function saveProfile() {
    setError(null);
    try {
      const p = await api.saveProfile({
        resume_text: resume,
      });
      setProfile(p);
      setStatus("Профиль сохранён");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  async function saveFields() {
    setError(null);
    try {
      if (fieldsHuntId) {
        const saved = await api.saveHuntFields(fieldsHuntId, fields);
        setFields(saved.custom_fields || fields);
        await refreshHunts();
      } else {
        const p = await api.saveProfile({ custom_fields: fields });
        setProfile(p);
        setFields(p.custom_fields || []);
      }
      setStatus("Поля сохранены");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  async function onFile(file: File) {
    const p = await api.uploadResume(file);
    setProfile(p);
    setResume(p.resume_text ?? "");
    setStatus(`Резюме из файла: ${p.resume_filename}`);
  }

  const TABS = [
    { id: "profile" as const, label: "Профиль" },
    { id: "fields" as const, label: "Поля карточки" },
    { id: "searches" as const, label: "Поиски" },
    { id: "notify" as const, label: "Уведомления" },
    ...(me?.is_host
      ? [
          { id: "calendar" as const, label: "Календарь" },
          { id: "telegram" as const, label: "Telegram" },
          { id: "people" as const, label: "Люди" },
          { id: "messages" as const, label: "Сообщения" },
        ]
      : []),
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex shrink-0 items-end px-7 pt-5 pb-4">
        <PageHead title="настройки" />
      </header>
      {error && <p className="mx-7 mb-3 text-sm text-rose-200">{error}</p>}
      {status && <p className="px-7 pb-2 text-[13px] text-accent">{status}</p>}

      <div className="flex min-h-0 flex-1 border-t border-line">
        <GuideSpot id="settings.tabs" className="w-[200px] shrink-0 overflow-y-auto border-r border-line py-2">
          <div className="flex justify-end px-3 pb-1">
            <GuideHint id="settings.tabs" />
          </div>
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`flex w-full px-5 py-2.5 text-left text-[14px] ${
                tab === item.id ? "bg-fill-strong text-ink" : "text-muted hover:bg-fill hover:text-ink"
              }`}
            >
              {item.label}
            </button>
          ))}
        </GuideSpot>
        <div className="min-w-0 flex-1 overflow-y-auto px-10 py-6">
          {tab === "profile" && (
            <div className="mx-auto w-full max-w-[480px] space-y-10 pt-4">
              <GuideSpot id="settings.resume">
              <section className="space-y-4">
                <div className="flex items-center gap-1.5">
                  <h2 className="text-[26px] font-semibold tracking-tight">Профиль</h2>
                  <GuideHint id="settings.resume" />
                </div>
                <p className="text-[13px] leading-5 text-muted">
                  Резюме правится в{" "}
                  <Link href="/resume" className="text-accent hover:underline">
                    кабинете
                  </Link>
                  . PDF можно залить здесь — текст попадёт в редактор.
                </p>
                <div className="flex items-center gap-3">
                  <label className="rounded-xl bg-fill-strong px-3 py-2 text-sm">
                    Загрузить PDF / TXT
                    <input
                      type="file"
                      accept=".pdf,.txt,.md"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void onFile(file);
                      }}
                    />
                  </label>
                  {profile?.resume_filename && <span className="text-sm text-muted">{profile.resume_filename}</span>}
                </div>
                <details className="text-[13px] text-muted">
                  <summary className="cursor-pointer hover:text-ink">сырой текст</summary>
                  <textarea
                    className="field-area mt-3"
                    rows={10}
                    value={resume}
                    onChange={(e) => setResume(e.target.value)}
                    placeholder="Если редактор ещё пуст — вставь текст сюда."
                  />
                  <button type="button" onClick={() => void saveProfile()} className="mt-3 text-[14px] text-accent">
                    Сохранить текст
                  </button>
                </details>
              </section>
              </GuideSpot>
              <section className="space-y-3">
                <h2 className="text-[18px] font-semibold tracking-tight">Клиппер</h2>
                <p className="text-[13px] leading-5 text-muted">
                  Chrome: chrome://extensions → «Режим разработчика» → «Загрузить распакованное» → папка{" "}
                  <code className="text-ink">extension/</code> в репозитории HuntOS. Сначала зайди в HuntOS в этом же
                  Chrome. Кнопка расширения кладёт текущую вкладку в inbox.
                </p>
                <p className="text-[13px] leading-5 text-muted">
                  С телефона — ссылка боту в Telegram. Или вставка URL в inbox.
                </p>
              </section>
            </div>
          )}

          {tab === "fields" && (
            <GuideSpot id="settings.fields">
            <HuntFieldsEditor
              fields={fields}
              onChange={setFields}
              onSave={() => void saveFields()}
              huntName={hunts.find((item) => item.id === fieldsHuntId)?.name}
              hunts={hunts}
              huntId={fieldsHuntId}
              onHuntId={setFieldsHuntId}
            />
            </GuideSpot>
          )}

          {tab === "calendar" && me?.is_host && (
            <GuideSpot id="settings.calendar">
              <GoogleCalendarPanel />
            </GuideSpot>
          )}
          {tab === "notify" && <TelegramBotPanel />}
          {tab === "telegram" && me?.is_host && (
            <GuideSpot id="settings.telegram">
              <TelegramPoolPanel user={me} />
            </GuideSpot>
          )}
          {tab === "people" && me?.is_host && (
            <GuideSpot id="settings.people">
              <div className="mx-auto w-full max-w-[480px] space-y-6 pt-4">
                <div>
                  <div className="flex items-center gap-1.5">
                    <h2 className="text-[26px] font-semibold tracking-tight">Люди</h2>
                    <GuideHint id="settings.people" />
                  </div>
                  <p className="mt-2 text-[13px] leading-5 text-muted">
                    Общий пул контактов в разделе Контакты — кнопка «все» — видишь только ты.
                  </p>
                </div>
                {users.filter((row) => row.id !== me.id).length === 0 && (
                  <p className="text-[14px] text-muted">Пока никто кроме тебя не зарегистрировался.</p>
                )}
                {users
                  .filter((row) => row.id !== me.id)
                  .map((row) => (
                    <label key={row.id} className="flex items-center justify-between gap-4 py-2">
                      <span className="min-w-0 truncate text-[14px]">{row.email}</span>
                      <input
                        type="checkbox"
                        checked={Boolean(row.can_observe)}
                        disabled={busyUser === row.id}
                        onChange={(e) => {
                          const next = e.target.checked;
                          setBusyUser(row.id);
                          void api
                            .patchUser(row.id, next)
                            .then(() => refreshUsers())
                            .finally(() => setBusyUser(null));
                        }}
                      />
                    </label>
                  ))}
              </div>
            </GuideSpot>
          )}
          {tab === "messages" && me?.is_host && (
            <div className="mx-auto w-full max-w-[480px] space-y-6 pt-4">
              <h2 className="text-[26px] font-semibold tracking-tight">Сообщения</h2>
              <FeedbackInbox />
            </div>
          )}

          {tab === "searches" && (
            <SearchesSettings isHost={Boolean(me?.is_host)} onStatus={setStatus} onError={setError} />
          )}
        </div>
      </div>
    </div>
  );
}
