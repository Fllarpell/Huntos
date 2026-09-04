"use client";

import { useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";

export function CompanyExcludeInput({
  value,
  onChange,
  placeholder = "яндекс, vk…",
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  function add(raw: string) {
    const name = raw.trim();
    if (name.length < 2) return;
    const key = name.toLowerCase().replaceAll("ё", "е");
    if (value.some((item) => item.toLowerCase().replaceAll("ё", "е") === key)) {
      setDraft("");
      return;
    }
    onChange([...value, name].slice(0, 32));
    setDraft("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft.replace(/,$/, ""));
    }
    if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {value.map((name) => (
        <button
          key={name}
          type="button"
          onClick={() => onChange(value.filter((item) => item !== name))}
          className="inline-flex items-center gap-1 text-[13px] text-rose-200/90 hover:text-rose-100"
        >
          {name}
          <X size={12} strokeWidth={2} />
        </button>
      ))}
      <input
        value={draft}
        onChange={(e) => {
          const next = e.target.value;
          if (next.includes(",")) {
            add(next.replace(/,/g, " "));
            return;
          }
          setDraft(next);
        }}
        onKeyDown={onKeyDown}
        onBlur={() => add(draft)}
        placeholder={value.length ? "ещё" : placeholder}
        className="min-w-[8rem] flex-1 !rounded-none !border-0 !bg-transparent !px-0 !py-1 text-[13px] !shadow-none outline-none placeholder:text-muted/70 focus:!border-transparent focus:!shadow-none"
      />
    </div>
  );
}
