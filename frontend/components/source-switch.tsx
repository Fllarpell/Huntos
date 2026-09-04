"use client";

import { useState } from "react";

export function Switch({
  on,
  onChange,
  disabled,
  label,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onChange(!on);
      }}
      className={`relative h-8 w-[52px] shrink-0 rounded-full border transition ${
        on ? "border-accent/40 bg-accent" : "border-white/10 bg-white/12"
      } ${disabled ? "cursor-not-allowed opacity-40" : "hover:brightness-110"}`}
    >
      <span
        className={`absolute top-[3px] h-[26px] w-[26px] rounded-full bg-white shadow-sm transition-[left] ${
          on ? "left-[22px]" : "left-[3px]"
        }`}
      />
    </button>
  );
}

export function SourceSwitchRow({
  name,
  hint,
  color,
  logo,
  on,
  onChange,
  onOpen,
  disabled,
}: {
  name: string;
  hint: string;
  color: string;
  logo?: string;
  on: boolean;
  onChange: (next: boolean) => void;
  onOpen?: () => void;
  disabled?: boolean;
}) {
  const [broken, setBroken] = useState(false);
  const showLogo = Boolean(logo && !broken);
  return (
    <div className="flex items-center gap-3 border-b border-white/[0.08] py-3.5">
      {showLogo ? (
        <img
          src={logo}
          alt=""
          width={28}
          height={28}
          className="h-7 w-7 shrink-0 rounded-lg bg-white/8 object-contain"
          onError={() => setBroken(true)}
        />
      ) : (
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      )}
      <button
        type="button"
        className="min-w-0 flex-1 rounded-lg text-left hover:text-white"
        onClick={() => onOpen?.()}
        disabled={!onOpen}
      >
        <p className="text-[17px] font-semibold leading-6 tracking-tight">{name}</p>
        {hint ? <p className="mt-0.5 text-[13px] leading-5 text-muted">{hint}</p> : null}
      </button>
      {onOpen ? (
        <button
          type="button"
          onClick={onOpen}
          className="shrink-0 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[13px] text-muted hover:border-white/20 hover:text-white"
        >
          ещё
        </button>
      ) : null}
      <Switch on={on} onChange={onChange} disabled={disabled} label={name} />
    </div>
  );
}
