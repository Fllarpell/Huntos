"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { FilterChips } from "@/components/filter-chips";
import { Switch } from "@/components/source-switch";
import {
  CATEGORIES,
  CONTACTS,
  ENGLISH,
  SORTS,
} from "@/lib/hirehi-filters";
import { HH_EMPLOYMENT, HH_PERIODS, HH_SORTS } from "@/lib/hh-filters";
import { appliesHint, type HuntSearch } from "@/lib/hunt-search";
import type { CareerBoard } from "@/lib/types";

export function SearchSourceSheet({
  pickKey,
  title,
  draft,
  onChange,
  boards: _boards,
  onClose,
}: {
  pickKey: string;
  title: string;
  draft: HuntSearch;
  onChange: (next: HuntSearch) => void;
  boards: CareerBoard[];
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const applied = appliesHint(pickKey, draft);

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <section
        className="flex h-full w-[min(420px,100%)] flex-col border-l border-line bg-bg-soft shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
          <div className="min-w-0">
            <p className="text-[12px] tracking-[0.12em] text-muted uppercase">Площадка</p>
            <h2 className="mt-1 text-[20px] font-semibold tracking-tight">{title}</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-muted hover:bg-white/6 hover:text-white">
            <X size={18} />
          </button>
        </header>
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <div className="rounded-xl bg-white/4 px-3 py-3">
            <p className="text-[12px] tracking-[0.12em] text-muted uppercase">Из общего поиска уйдёт</p>
            <p className="mt-1 text-[14px] leading-5">{applied}</p>
          </div>

          {pickKey === "hirehi" ? (
            <>
              <label className="block space-y-2">
                <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Категория HireHi</span>
                <select
                  value={draft.hirehiCategory}
                  onChange={(e) => onChange({ ...draft, hirehiCategory: e.target.value })}
                >
                  {CATEGORIES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Английский</legend>
                <FilterChips
                  variant="pill"
                  options={ENGLISH}
                  value={draft.hirehiEnglish}
                  onChange={(hirehiEnglish) => onChange({ ...draft, hirehiEnglish })}
                />
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Контакт</legend>
                <FilterChips
                  variant="pill"
                  options={CONTACTS}
                  value={draft.hirehiContacts}
                  onChange={(hirehiContacts) => onChange({ ...draft, hirehiContacts })}
                />
              </fieldset>
              <label className="block space-y-2">
                <span className="text-[12px] tracking-[0.12em] text-muted uppercase">Сортировка</span>
                <select value={draft.hirehiSort} onChange={(e) => onChange({ ...draft, hirehiSort: e.target.value })}>
                  {SORTS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}

          {pickKey === "hh" ? (
            <>
              <fieldset className="space-y-2">
                <legend className="text-[12px] tracking-[0.12em] text-muted uppercase">Занятость</legend>
                <FilterChips
                  variant="pill"
                  options={HH_EMPLOYMENT}
                  value={draft.hhEmployment}
                  onChange={(hhEmployment) => onChange({ ...draft, hhEmployment })}
                />
              </fieldset>
              <div className="grid grid-cols-1 gap-3">
                <label className="space-y-2">
                  <span className="block text-[12px] tracking-[0.12em] text-muted uppercase">Сортировка</span>
                  <select value={draft.hhOrderBy} onChange={(e) => onChange({ ...draft, hhOrderBy: e.target.value })}>
                    {HH_SORTS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-2">
                  <span className="block text-[12px] tracking-[0.12em] text-muted uppercase">Период</span>
                  <select value={draft.hhPeriod} onChange={(e) => onChange({ ...draft, hhPeriod: e.target.value })}>
                    {HH_PERIODS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="flex items-center justify-between gap-4 border-b border-white/[0.08] py-3">
                <div>
                  <p className="text-[15px] font-medium">Показать Chrome</p>
                  <p className="mt-0.5 text-[13px] text-muted">Нужно, если hh покажет капчу</p>
                </div>
                <Switch
                  on={draft.hhHeaded}
                  onChange={(hhHeaded) => onChange({ ...draft, hhHeaded })}
                  label="Показать Chrome"
                />
              </div>
            </>
          ) : null}
        </div>
      </section>
    </div>
  );
}
