"use client";

type Option = { value: string; label: string };

const chipClass = (on: boolean) =>
  `text-[13px] leading-6 transition ${on ? "text-accent" : "text-muted hover:text-white"}`;

export function FilterChips({
  options,
  value,
  onChange,
}: {
  options: readonly Option[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {options.map((option) => {
        const on = value.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            onClick={() =>
              onChange(on ? value.filter((item) => item !== option.value) : [...value, option.value])
            }
            className={chipClass(on)}
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
}: {
  options: readonly Option[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={chipClass(value === option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function ToggleChip({
  label,
  on,
  onChange,
}: {
  label: string;
  on: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button type="button" onClick={() => onChange(!on)} className={chipClass(on)}>
      {label}
    </button>
  );
}
