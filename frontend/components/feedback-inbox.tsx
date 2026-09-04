"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { pageLabel } from "@/lib/feedback-pages";
import { relativeTime } from "@/lib/format";

type Note = {
  id: number;
  kind: string;
  body: string;
  page: string | null;
  contact_name: string | null;
  reply_to: string | null;
  email: string;
  created_at: string;
};

export function FeedbackInbox() {
  const [rows, setRows] = useState<Note[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .feedback()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Не загрузилось"));
  }, []);

  if (error) return <p className="text-sm text-rose-200">{error}</p>;
  if (rows == null) return <p className="text-[14px] text-muted">…</p>;
  if (rows.length === 0) return <p className="text-[14px] text-muted">Пока пусто</p>;

  return (
    <div className="space-y-6">
      {rows.map((row) => (
        <article key={row.id} className="border-b border-white/[0.06] pb-5">
          <p className="text-[13px] text-white/85">
            {row.kind === "bug" ? "ошибка" : "пожелание"}
            {" · "}
            {pageLabel(row.page) || "экран не указан"}
          </p>
          <p className="mt-0.5 text-[13px] text-muted">
            {row.contact_name || row.email}
            {" · "}
            {relativeTime(row.created_at)}
          </p>
          {row.reply_to && row.reply_to !== row.email ? (
            <p className="mt-1 text-[12px] text-muted">ответ: {row.reply_to}</p>
          ) : null}
          <p className="mt-2 whitespace-pre-wrap text-[15px] leading-6">{row.body}</p>
        </article>
      ))}
    </div>
  );
}
