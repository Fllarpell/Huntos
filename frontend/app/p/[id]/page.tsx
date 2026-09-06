"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ResumeSheet } from "@/components/resume-sheet";
import { api } from "@/lib/api";
import { normalizeResume, type ResumeDoc } from "@/lib/resume";

export default function PublicCvPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const [doc, setDoc] = useState<ResumeDoc | null>(null);
  const [adapted, setAdapted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = String(params.id || "").trim();
    if (!id) {
      setError("Нет такого профиля");
      return;
    }
    const rawTarget = search.get("target") || "";
    const target = Number(rawTarget);
    api
      .publicCv(id, Number.isFinite(target) && target > 0 ? target : null)
      .then((row) => {
        setDoc(normalizeResume(row.resume));
        setAdapted(row.adapted);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Резюме не найдено"));
  }, [params.id, search]);

  return (
    <div className="min-h-full bg-[#ececec] px-4 py-8">
      <div className="mx-auto max-w-[21cm]">
        {error ? <p className="text-[14px] text-neutral-600">{error}</p> : null}
        {doc ? <ResumeSheet doc={doc} /> : error ? null : <p className="text-[14px] text-neutral-500">загрузка…</p>}
        {doc ? (
          <p className="mt-6 text-center text-[12px] text-neutral-500">
            {adapted ? "под эту вакансию · " : ""}
            <a href="/" className="underline">
              HuntOS
            </a>
          </p>
        ) : null}
      </div>
    </div>
  );
}
