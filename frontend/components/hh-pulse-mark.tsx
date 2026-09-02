import { hhPulseLabel } from "@/lib/format";

export function HhPulseMark({
  pulse,
  className = "",
}: {
  pulse?: string | null;
  className?: string;
}) {
  const label = hhPulseLabel(pulse);
  if (!label) return null;
  const tone = pulse === "discarded" ? "text-rose-200" : "text-emerald-200";
  return <span className={`shrink-0 tabular-nums ${tone} ${className}`}>{label}</span>;
}
