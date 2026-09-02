import { formatNextStepBadge } from "@/lib/format";

export function NextStepBadge({
  at,
  kind,
  collide,
  hint,
}: {
  at: string | null | undefined;
  kind?: string | null;
  collide?: boolean;
  hint?: string | null;
}) {
  const label = formatNextStepBadge(at, kind);
  if (!label) return null;
  return (
    <span
      title={hint || undefined}
      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] tabular-nums ${
        collide ? "bg-amber-400/15 text-amber-200" : "bg-accent/12 text-accent"
      }`}
    >
      {label}
    </span>
  );
}
