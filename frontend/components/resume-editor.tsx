"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { GuideHint, GuideSpot } from "@/components/guide";
import { PageHead } from "@/components/page-head";
import { ResumeSheet } from "@/components/resume-sheet";
import {
  bulletsToText,
  emptyResume,
  linesToText,
  normalizeResume,
  textToBullets,
  textToLines,
  tidyLine,
  type ResumeAboutItem,
  type ResumeDoc,
  type ResumeJob,
  type ResumeSchool,
  type ResumeSkillGroup,
} from "@/lib/resume";

function compactDoc(doc: ResumeDoc): ResumeDoc {
  return {
    ...doc,
    about_items: doc.about_items.filter((item) => item.label.trim() || item.text.trim()),
    skill_groups: doc.skill_groups.filter((g) => g.label.trim() || g.items.trim()),
    experience: doc.experience
      .map((job) => ({
        ...job,
        bullets: job.bullets
          .map((b) => ({
            text: tidyLine(b.text),
            children: b.children.map(tidyLine).filter(Boolean),
          }))
          .filter((b) => b.text || b.children.length),
      }))
      .filter((job) => job.company || job.title || job.bullets.length),
    education: doc.education
      .map((row) => ({ ...row, bullets: row.bullets.map((item) => item.trim()).filter(Boolean) }))
      .filter((row) => row.school || row.degree || row.bullets.length),
    courses: doc.courses.map((item) => item.trim()).filter(Boolean),
    hackathons: doc.hackathons.map((item) => item.trim()).filter(Boolean),
    links: doc.links.map((item) => item.trim()).filter(Boolean),
  };
}

export function ResumeEditor() {
  const [doc, setDoc] = useState<ResumeDoc>(emptyResume());
  const [filename, setFilename] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [shareOn, setShareOn] = useState(false);
  const [shareId, setShareId] = useState<string | null>(null);
  const [shareBusy, setShareBusy] = useState(false);

  function applyShare(profile: { resume_public?: boolean; resume_share_id?: string | null }) {
    setShareOn(Boolean(profile.resume_public));
    setShareId(profile.resume_share_id || null);
  }

  async function load() {
    const profile = await api.profile();
    setDoc(
      normalizeResume(
        profile.resume_json || { summary: profile.resume_text || "", name: profile.display_name || "" },
      ),
    );
    setFilename(profile.resume_filename);
    applyShare(profile);
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Не загрузилось"));
  }, []);

  function patch(part: Partial<ResumeDoc>) {
    setDoc((prev) => ({ ...prev, ...part }));
  }

  function setJob(index: number, part: Partial<ResumeJob>) {
    setDoc((prev) => ({
      ...prev,
      experience: prev.experience.map((job, i) => (i === index ? { ...job, ...part } : job)),
    }));
  }

  function setSchool(index: number, part: Partial<ResumeSchool>) {
    setDoc((prev) => ({
      ...prev,
      education: prev.education.map((row, i) => (i === index ? { ...row, ...part } : row)),
    }));
  }

  function setAbout(index: number, part: Partial<ResumeAboutItem>) {
    setDoc((prev) => ({
      ...prev,
      about_items: prev.about_items.map((item, i) => (i === index ? { ...item, ...part } : item)),
    }));
  }

  function setGroup(index: number, part: Partial<ResumeSkillGroup>) {
    setDoc((prev) => ({
      ...prev,
      skill_groups: prev.skill_groups.map((item, i) => (i === index ? { ...item, ...part } : item)),
    }));
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const profile = await api.saveProfile({ resume_json: compactDoc(doc) });
      setDoc(normalizeResume(profile.resume_json));
      setStatus("Сохранено");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сохранилось");
    } finally {
      setBusy(false);
    }
  }

  async function setShare(next: boolean) {
    setShareBusy(true);
    setError(null);
    try {
      applyShare(await api.saveProfile({ resume_public: next }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не сохранилось");
    } finally {
      setShareBusy(false);
    }
  }

  async function onFile(file: File) {
    setError(null);
    setBusy(true);
    try {
      const profile = await api.uploadResume(file);
      const next = normalizeResume(profile.resume_json || { summary: profile.resume_text || "" });
      setDoc(next);
      setFilename(profile.resume_filename);
      const structured = next.experience.length > 0 || next.skill_groups.some((g) => g.items);
      setStatus(
        structured
          ? `Разобрал в поля: ${profile.resume_filename}`
          : `Текст из файла: ${profile.resume_filename}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Файл не прочитался");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="shrink-0 px-5 pt-5 pb-4 md:px-7 print:hidden">
        <PageHead title="резюме" hint={<GuideHint id="resume.editor" />}>
          <label className={`text-[13px] text-muted hover:text-ink ${busy ? "pointer-events-none opacity-40" : "cursor-pointer"}`}>
            PDF / TXT
            <input
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void onFile(file);
              }}
            />
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() => void save()}
            className="text-[13px] text-accent disabled:opacity-40"
          >
            {busy ? "подожди…" : "сохранить"}
          </button>
          <button type="button" onClick={() => window.print()} className="text-[13px] text-muted hover:text-ink">
            PDF
          </button>
        </PageHead>
        <label className="mt-3 flex items-center gap-2 text-[13px] text-muted">
          <input
            type="checkbox"
            checked={shareOn}
            disabled={shareBusy}
            onChange={(e) => void setShare(e.target.checked)}
          />
          открыть по ссылке
        </label>
        {shareOn && shareId ? (
          <p className="mt-1 text-[12px] text-muted">
            <a href={`/p/${shareId}`} className="underline hover:text-ink" target="_blank" rel="noreferrer">
              /p/{shareId}
            </a>
          </p>
        ) : null}
        {filename ? <p className="mt-2 text-[12px] text-muted">{filename}</p> : null}
        {error ? <p className="mt-2 text-sm text-rose-200">{error}</p> : null}
        {status ? <p className="mt-2 text-[13px] text-accent">{status}</p> : null}
      </header>

      <div className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-2">
        <GuideSpot id="resume.editor" className="min-h-0 overflow-y-auto border-t border-line px-5 py-6 md:px-7 print:hidden">
          <div className="mx-auto w-full max-w-[520px] space-y-9">
            <section className="space-y-3">
              <input
                className="field-line text-[22px] font-semibold"
                value={doc.name}
                onChange={(e) => patch({ name: e.target.value })}
                placeholder="Имя"
              />
              <input
                className="field-line"
                value={doc.headline}
                onChange={(e) => patch({ headline: e.target.value })}
                placeholder="ML Engineer"
              />
              <input
                className="field-line"
                value={doc.location}
                onChange={(e) => patch({ location: e.target.value })}
                placeholder="город"
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  className="field-line"
                  value={doc.phone}
                  onChange={(e) => patch({ phone: e.target.value })}
                  placeholder="телефон"
                />
                <input
                  className="field-line"
                  value={doc.telegram}
                  onChange={(e) => patch({ telegram: e.target.value })}
                  placeholder="@telegram"
                />
              </div>
              <input
                className="field-line"
                value={doc.email}
                onChange={(e) => patch({ email: e.target.value })}
                placeholder="email"
              />
              <textarea
                className="field-area min-h-[64px]"
                value={linesToText(doc.links)}
                onChange={(e) => patch({ links: textToLines(e.target.value) })}
                placeholder="ещё ссылки — github, сайт"
              />
            </section>

            <section className="space-y-3">
              <h2 className="text-[12px] text-muted">обо мне</h2>
              <textarea
                className="field-area min-h-[120px]"
                value={doc.summary}
                onChange={(e) => patch({ summary: e.target.value })}
                placeholder="Абзац до списка. Как в LaTeX до itemize."
              />
              {doc.about_items.map((item, index) => (
                <div key={index} className="grid gap-2 sm:grid-cols-[140px_1fr]">
                  <input
                    className="field-line"
                    value={item.label}
                    onChange={(e) => setAbout(index, { label: e.target.value })}
                    placeholder="Ответственность"
                  />
                  <textarea
                    className="field-area min-h-[64px]"
                    value={item.text}
                    onChange={(e) => setAbout(index, { text: e.target.value })}
                    placeholder="текст пункта"
                  />
                </div>
              ))}
              <button
                type="button"
                className="text-[13px] text-accent"
                onClick={() =>
                  setDoc((prev) => ({ ...prev, about_items: [...prev.about_items, { label: "", text: "" }] }))
                }
              >
                пункт
              </button>
            </section>

            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-[12px] text-muted">технические навыки</h2>
                <button
                  type="button"
                  className="text-[13px] text-accent"
                  onClick={() =>
                    setDoc((prev) => ({
                      ...prev,
                      skill_groups: [...prev.skill_groups, { label: "", items: "" }],
                    }))
                  }
                >
                  группа
                </button>
              </div>
              {doc.skill_groups.map((group, index) => (
                <div key={index} className="space-y-1">
                  <input
                    className="field-line"
                    value={group.label}
                    onChange={(e) => setGroup(index, { label: e.target.value })}
                    placeholder="Python"
                  />
                  <textarea
                    className="field-area min-h-[52px]"
                    value={group.items}
                    onChange={(e) => setGroup(index, { items: e.target.value })}
                    placeholder="AsyncIO, FastAPI, SQLAlchemy 2.0"
                  />
                </div>
              ))}
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-[12px] text-muted">опыт</h2>
                <button
                  type="button"
                  className="text-[13px] text-accent"
                  onClick={() =>
                    setDoc((prev) => ({
                      ...prev,
                      experience: [
                        ...prev.experience,
                        { company: "", title: "", period: "", context: "", bullets: [{ text: "", children: [] }] },
                      ],
                    }))
                  }
                >
                  место
                </button>
              </div>
              {doc.experience.map((job, index) => (
                <div key={index} className="space-y-2 rounded-2xl border border-line px-4 py-4">
                  {doc.experience.length > 1 ? (
                    <div className="flex justify-end">
                      <button
                        type="button"
                        className="text-[12px] text-muted hover:text-ink"
                        onClick={() =>
                          setDoc((prev) => ({
                            ...prev,
                            experience: prev.experience.filter((_, i) => i !== index),
                          }))
                        }
                      >
                        убрать
                      </button>
                    </div>
                  ) : null}
                  <input
                    className="field-line"
                    value={job.company}
                    onChange={(e) => setJob(index, { company: e.target.value })}
                    placeholder="компания"
                  />
                  <input
                    className="field-line"
                    value={job.period}
                    onChange={(e) => setJob(index, { period: e.target.value })}
                    placeholder="Сентябрь 2024 — Август 2026"
                  />
                  <input
                    className="field-line"
                    value={job.title}
                    onChange={(e) => setJob(index, { title: e.target.value })}
                    placeholder="должность"
                  />
                  <input
                    className="field-line"
                    value={job.context}
                    onChange={(e) => setJob(index, { context: e.target.value })}
                    placeholder="B2B SaaS / университетский проект"
                  />
                  <textarea
                    className="field-area min-h-[140px]"
                    value={bulletsToText(job.bullets)}
                    onChange={(e) => setJob(index, { bullets: textToBullets(e.target.value) })}
                    placeholder={"**RAG.** Спроектировал пайплайн…\n  вложенный пункт с отступом"}
                  />
                </div>
              ))}
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-[12px] text-muted">образование</h2>
                <button
                  type="button"
                  className="text-[13px] text-accent"
                  onClick={() =>
                    setDoc((prev) => ({
                      ...prev,
                      education: [...prev.education, { school: "", degree: "", period: "", bullets: [] }],
                    }))
                  }
                >
                  строка
                </button>
              </div>
              {doc.education.map((row, index) => (
                <div key={index} className="space-y-2">
                  <input
                    className="field-line"
                    value={row.school}
                    onChange={(e) => setSchool(index, { school: e.target.value })}
                    placeholder="вуз"
                  />
                  <input
                    className="field-line"
                    value={row.period}
                    onChange={(e) => setSchool(index, { period: e.target.value })}
                    placeholder="2023 — 2027"
                  />
                  <input
                    className="field-line"
                    value={row.degree}
                    onChange={(e) => setSchool(index, { degree: e.target.value })}
                    placeholder="Бакалавр, Data Science"
                  />
                  <textarea
                    className="field-area min-h-[64px]"
                    value={linesToText(row.bullets)}
                    onChange={(e) => setSchool(index, { bullets: textToLines(e.target.value) })}
                    placeholder="Дипломный проект: …"
                  />
                </div>
              ))}
            </section>

            <section className="space-y-2">
              <h2 className="text-[12px] text-muted">повышение квалификации</h2>
              <textarea
                className="field-area min-h-[72px]"
                value={linesToText(doc.courses)}
                onChange={(e) => patch({ courses: textToLines(e.target.value) })}
                placeholder="по курсу на строку"
              />
            </section>

            <section className="space-y-2 pb-10">
              <h2 className="text-[12px] text-muted">хакатоны</h2>
              <textarea
                className="field-area min-h-[64px]"
                value={linesToText(doc.hackathons)}
                onChange={(e) => patch({ hackathons: textToLines(e.target.value) })}
                placeholder="CodeStorm, AIOS…"
              />
            </section>
          </div>
        </GuideSpot>

        <div className="resume-stage min-h-0 overflow-y-auto border-t border-line px-4 py-6 md:px-8 print:overflow-visible print:border-0 print:bg-white print:p-0">
          <ResumeSheet doc={doc} />
        </div>
      </div>
    </div>
  );
}
