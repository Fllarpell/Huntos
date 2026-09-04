"use client";

import { useMemo, useState } from "react";
import { SEARCH_CITIES, SEARCH_CITY_HUBS, nextSearchCities } from "@/lib/hunt-cities";

type Option = { value: string; label: string };
type Variant = "text" | "pill" | "chip";

const chipClass = (on: boolean, variant: Variant = "text") => {
  if (variant === "pill") {
    return `rounded-xl border px-3.5 py-2 text-[13px] leading-5 transition ${
      on
        ? "border-accent/45 bg-accent/15 text-accent"
        : "border-white/10 bg-white/[0.04] text-muted hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
    }`;
  }
  if (variant === "chip") {
    return `rounded-full border px-2.5 py-1 text-[12px] leading-4 transition ${
      on
        ? "border-accent/50 bg-accent/15 text-accent"
        : "border-white/10 text-muted hover:border-white/25 hover:bg-white/[0.06] hover:text-white"
    }`;
  }
  return `text-[13px] leading-6 transition ${on ? "text-accent" : "text-muted hover:text-white"}`;
};

function chipGap(variant: Variant) {
  return variant === "text" ? "gap-x-4 gap-y-1" : "gap-1.5";
}

export function FilterChips({
  options,
  value,
  onChange,
  variant = "text",
}: {
  options: readonly Option[];
  value: string[];
  onChange: (next: string[]) => void;
  variant?: Variant;
}) {
  return (
    <div className={`flex flex-wrap items-center ${chipGap(variant)}`}>
      {options.map((option) => {
        const on = value.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            onClick={() =>
              onChange(on ? value.filter((item) => item !== option.value) : [...value, option.value])
            }
            className={chipClass(on, variant)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function ChoiceChips({
  options,
  value,
  onChange,
  variant = "text",
}: {
  options: readonly Option[];
  value: string;
  onChange: (next: string) => void;
  variant?: Variant;
}) {
  return (
    <div className={`flex flex-wrap items-center ${chipGap(variant)}`}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={chipClass(value === option.value, variant)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function OverflowFilterChips({
  options,
  value,
  onChange,
  preview = 10,
  searchPlaceholder,
}: {
  options: readonly Option[];
  value: string[];
  onChange: (next: string[]) => void;
  preview?: number;
  searchPlaceholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const selected = options.filter((option) => value.includes(option.value));
  const rest = options.filter((option) => !value.includes(option.value));
  const needle = q.trim().toLowerCase();
  const matched = needle
    ? rest.filter((option) => option.label.toLowerCase().includes(needle))
    : rest;
  const room = Math.max(0, preview - selected.length);
  const visibleRest = open ? matched : matched.slice(0, room);
  const hidden = rest.length - (open ? rest.length : Math.min(rest.length, room));

  return (
    <div className="space-y-2">
      <FilterChips options={[...selected, ...visibleRest]} value={value} onChange={onChange} variant="chip" />
      {hidden > 0 || open ? (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => setOpen((cur) => !cur)} className="text-[12px] text-muted hover:text-white">
            {open ? "свернуть" : `ещё ${hidden}`}
          </button>
          {open && searchPlaceholder && rest.length > preview ? (
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={searchPlaceholder}
              className="max-w-[16rem] !rounded-full !px-3 !py-1.5 text-[12px]"
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function ToggleChip({
  label,
  on,
  onChange,
  disabled,
  marked,
}: {
  label: string;
  on: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  marked?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`${chipClass(on)} ${marked ? "underline decoration-accent/70 underline-offset-[6px]" : ""} ${
        disabled ? "cursor-not-allowed opacity-40 hover:text-muted" : ""
      }`}
    >
      {label}
    </button>
  );
}

export function CityPicker({
  value,
  onChange,
  variant = "pill",
}: {
  value: string[];
  onChange: (next: string[]) => void;
  variant?: Variant;
}) {
  const [more, setMore] = useState(false);
  const [q, setQ] = useState("");
  const byId = useMemo(
    () => new Map<string, (typeof SEARCH_CITIES)[number]>(SEARCH_CITIES.map((item) => [item.value, item])),
    [],
  );
  const hubSet = useMemo(() => new Set<string>(SEARCH_CITY_HUBS), []);
  const shown = useMemo(() => {
    const ids = [...SEARCH_CITY_HUBS, ...value.filter((id) => !hubSet.has(id))];
    return ids
      .map((id) => byId.get(id))
      .filter((item): item is (typeof SEARCH_CITIES)[number] => Boolean(item));
  }, [byId, hubSet, value]);
  const matches = useMemo(() => {
    const shownIds = new Set(shown.map((item) => item.value));
    const needle = q.trim().toLowerCase();
    if (!needle) return [];
    return SEARCH_CITIES.filter(
      (item) => !shownIds.has(item.value) && item.label.toLowerCase().includes(needle),
    );
  }, [q, shown]);
  const hiddenCount = SEARCH_CITIES.length - shown.length;

  function setCities(next: string[]) {
    onChange(nextSearchCities(value, next));
  }

  return (
    <div className="space-y-2">
      <FilterChips options={shown} value={value} onChange={setCities} variant={variant} />
      <button type="button" onClick={() => setMore((open) => !open)} className="text-[13px] text-muted hover:text-white">
        {more ? "свернуть города" : `ещё ${hiddenCount} городов`}
      </button>
      {more ? (
        <div className="space-y-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Томск, Калуга, Пермь…" className="w-full" />
          {q.trim() ? (
            matches.length ? (
              <FilterChips options={matches} value={value} onChange={setCities} variant={variant} />
            ) : (
              <p className="text-[13px] text-muted">нет такого города в списке</p>
            )
          ) : (
            <p className="text-[13px] text-muted">начни вводить название</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
