const LABELS: Record<string, string> = {
  hirehi: "HireHi",
  hh: "hh.ru",
  hh_career: "hh.ru зарплаты",
  habr: "Habr Career",
  habr_career: "Хабр Карьера",
  getmatch: "GetMatch",
  getmatch_salaries: "GetMatch зарплаты",
  "levels.fyi": "Levels.fyi",
  geekjob: "GeekJob",
  career: "Компании",
  telegram: "Telegram",
  manual: "вручную",
  clip: "клиппер",
};

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return "";
  return LABELS[source] ?? source;
}

type ExtraSource = { source?: string; source_id?: string; source_url?: string; label?: string };

function sourceIdentity(source?: string | null, sourceId?: string | null): string {
  const src = (source || "").trim();
  if (src === "career") {
    const slug = (sourceId || "").split(":", 1)[0].trim();
    return slug ? `career:${slug}` : "career";
  }
  return src;
}

export function uniqueExtraSources(
  extras: ExtraSource[] | null | undefined,
  primary?: { source?: string | null; source_id?: string | null },
): ExtraSource[] {
  const seen = new Set<string>();
  const primaryKey = sourceIdentity(primary?.source, primary?.source_id);
  if (primaryKey) seen.add(primaryKey);
  const primaryLabel = (primary?.source === "manual" ? "вручную" : sourceLabel(primary?.source)).toLowerCase();
  const out: ExtraSource[] = [];
  for (const src of extras || []) {
    const label = (src.label || sourceLabel(src.source) || "").trim();
    if (!label) continue;
    const key = sourceIdentity(src.source, src.source_id) || label.toLowerCase();
    if (seen.has(key)) continue;
    if (label.toLowerCase() === primaryLabel) continue;
    if (out.some((item) => (item.label || sourceLabel(item.source) || "").toLowerCase() === label.toLowerCase())) {
      continue;
    }
    seen.add(key);
    out.push(src);
  }
  const named = out.filter((item) => (item.label || sourceLabel(item.source)) !== "Компании");
  return named.length ? named : out;
}

export function extraSourcesLine(v: {
  source?: string | null;
  source_id?: string | null;
  extra_sources?: ExtraSource[];
}): string {
  const labels = uniqueExtraSources(v.extra_sources, v).map((src) => src.label || sourceLabel(src.source));
  return labels.length ? `повтор ${labels.join(" + ")}` : "";
}

export function SourceBadge({
  source,
  label,
}: {
  source: string | null | undefined;
  label?: string;
}) {
  const text = label || sourceLabel(source);
  if (!text) return null;
  return (
    <span className="inline-flex shrink-0 items-center rounded-md bg-white/6 px-1.5 py-0.5 text-[10px] tracking-[0.04em] text-muted uppercase">
      {text}
    </span>
  );
}
