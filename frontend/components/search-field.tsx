"use client";

import type { Ref } from "react";
import { Search } from "lucide-react";

export function SearchField({
  value,
  onChange,
  placeholder,
  inputRef,
  className = "min-w-[200px] max-w-xs flex-1",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  inputRef?: Ref<HTMLInputElement>;
  className?: string;
}) {
  return (
    <label className={`flex items-center gap-2 rounded-full bg-white/[0.04] px-3 py-2 ${className}`}>
      <Search size={14} strokeWidth={1.75} className="shrink-0 text-muted" />
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="min-w-0 flex-1 !rounded-none !border-0 !bg-transparent !p-0 text-[13px] !shadow-none focus:!border-transparent focus:!shadow-none"
      />
    </label>
  );
}
