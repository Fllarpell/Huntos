import { matchTone } from "@/lib/format";

export function MatchBadge({
  score,
  status,
  size = "md",
}: {
  score: number | null;
  status?: string;
  size?: "sm" | "md";
}) {
  const tone = matchTone(score);
  if (score == null && status !== "pending") return null;
  const label = score == null ? "…" : `${score}`;
  const cls = {
    high: "bg-emerald-400/12 text-emerald-300 ring-emerald-400/20",
    mid: "bg-amber-400/12 text-amber-200 ring-amber-400/20",
    low: "bg-rose-400/12 text-rose-300 ring-rose-400/20",
    none: "bg-white/6 text-muted ring-white/8",
  }[tone];
  const dim = size === "sm" ? "h-6 min-w-6 px-1.5 text-[11px]" : "h-8 min-w-8 px-2 text-[13px]";
  return (
    <span className={`inline-flex items-center justify-center rounded-full font-medium ring-1 ${dim} ${cls}`}>
      {label}
    </span>
  );
}
