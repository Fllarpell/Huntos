const LABELS: Record<string, string> = {
  hirehi: "HireHi",
  hh: "hh.ru",
  telegram: "Telegram",
  manual: "вручную",
  clip: "клиппер",
};

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return "";
  return LABELS[source] ?? source;
}

export function SourceBadge({ source }: { source: string | null | undefined }) {
  const label = sourceLabel(source);
  if (!label) return null;
  return (
    <span className="inline-flex shrink-0 items-center rounded-md bg-white/6 px-1.5 py-0.5 text-[10px] tracking-[0.04em] text-muted uppercase">
      {label}
    </span>
  );
}
