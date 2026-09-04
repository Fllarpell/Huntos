import { SUBCATEGORIES, LEVELS, CATEGORIES } from "@/lib/hirehi-filters";

export type SalaryCorridor = {
  n: number;
  n_vacancies?: number;
  n_aggregators?: number;
  p25: number | null;
  median: number | null;
  p75: number | null;
  currency?: string;
  open_share?: number | null;
  by_source?: Record<string, number>;
  key?: string;
  label?: string;
  by_grade?: SalaryCorridor[];
  by_specialty?: SalaryCorridor[];
};

export const CORRIDOR_MIN_N = 3;

export const LEVELS_FYI_URL = "https://www.levels.fyi/t/software-engineer/locations/russia";
export const HABR_SALARIES_URL = "https://career.habr.com/salaries";
export const GETMATCH_SALARIES_URL = "https://getmatch.ru/salaries";

const GRADE_ORDER = ["intern", "junior", "middle", "senior", "lead", "head"] as const;

const GRADE_ALIASES: Record<string, string> = {
  intern: "intern",
  internship: "intern",
  junior: "junior",
  jr: "junior",
  middle: "middle",
  mid: "middle",
  senior: "senior",
  sr: "senior",
  lead: "lead",
  teamlead: "lead",
  "team-lead": "lead",
  techlead: "lead",
  "tech-lead": "lead",
  head: "head",
  principal: "head",
  staff: "head",
};

const SPECIALTY_LABELS: Record<string, string> = {
  ...Object.fromEntries(SUBCATEGORIES.map((item) => [item.value, item.label])),
  ...Object.fromEntries(CATEGORIES.map((item) => [item.value, item.label])),
  go: "Go",
  python: "Python",
  java: "Java",
  frontend: "Frontend",
  backend: "Backend",
  devops: "DevOps",
  unknown: "без специальности",
};

export function corridorReady(c: SalaryCorridor | null | undefined): boolean {
  return Boolean(c && c.n > 0 && c.p25 != null && c.median != null && c.p75 != null);
}

export function formatCorridorK(n: number): string {
  if (n >= 1000) {
    const k = n / 1000;
    const text = Number.isInteger(k) ? String(k) : k.toFixed(1).replace(/\.0$/, "");
    return `${text}к`;
  }
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

export function corridorLabel(c: SalaryCorridor): string {
  if (c.p25 == null || c.median == null || c.p75 == null) return "—";
  return `${formatCorridorK(c.p25)}–${formatCorridorK(c.median)}–${formatCorridorK(c.p75)}`;
}

export function formatSourceBreakdown(
  bySource: Record<string, number> | null | undefined,
  labelOf: (source: string) => string,
): string {
  if (!bySource) return "";
  return Object.entries(bySource)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([source, n]) => `${labelOf(source) || source} ${n}`)
    .join(" · ");
}

function normalizeGrade(raw: string | null | undefined): string {
  const text = (raw || "").trim().toLowerCase();
  if (!text) return "unknown";
  if (GRADE_ALIASES[text]) return GRADE_ALIASES[text];
  for (const [alias, canon] of Object.entries(GRADE_ALIASES)) {
    if (text.includes(alias)) return canon;
  }
  return "unknown";
}

function specialtyOf(row: {
  title?: string | null;
  skills?: string[] | null;
  category?: string | null;
}): string {
  const skills = row.skills || [];
  for (const skill of skills) {
    const key = skill.trim().toLowerCase();
    if (SPECIALTY_LABELS[key] || SUBCATEGORIES.some((item) => item.value === key)) return key;
  }
  const blob = `${row.title || ""} ${skills.join(" ")} ${row.category || ""}`.toLowerCase();
  for (const item of SUBCATEGORIES) {
    if (blob.includes(item.value.replace("_", " ")) || blob.includes(item.label.toLowerCase())) {
      return item.value;
    }
    if (item.value === "python" && blob.includes("python")) return "python";
    if (item.value === "frontend" && (blob.includes("frontend") || blob.includes("react"))) return "frontend";
    if (item.value === "backend" && blob.includes("backend")) return "backend";
    if (item.value === "go" && (blob.includes("golang") || /\bgo\b/.test(blob))) return "go";
  }
  const cat = (row.category || "").trim().toLowerCase();
  if (cat && SPECIALTY_LABELS[cat]) return cat;
  return "unknown";
}

function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  if (ordered.length === 1) return ordered[0];
  const rank = (ordered.length - 1) * (p / 100);
  const low = Math.floor(rank);
  const high = Math.min(low + 1, ordered.length - 1);
  if (low === high) return ordered[low];
  const frac = rank - low;
  return Math.round(ordered[low] + (ordered[high] - ordered[low]) * frac);
}

function buildCorridor(
  values: number[],
  bySource: Record<string, number>,
  openN: number,
  key?: string,
  label?: string,
): SalaryCorridor {
  const n = values.length;
  return {
    n,
    p25: n ? percentile(values, 25) : null,
    median: n ? percentile(values, 50) : null,
    p75: n ? percentile(values, 75) : null,
    currency: "RUB",
    open_share: n ? Math.round((openN / n) * 100) / 100 : null,
    by_source: bySource,
    key,
    label,
  };
}

/** Client-side corridor from loaded vacancies (inbox). */
export function corridorFromVacancies(
  rows: {
    salary_min?: number | null;
    salary_currency?: string | null;
    source?: string | null;
    grade?: string | null;
    title?: string | null;
    skills?: string[] | null;
    category?: string | null;
  }[],
): SalaryCorridor {
  const amounts: number[] = [];
  const bySource: Record<string, number> = {};
  const gradeBuckets = new Map<string, { amounts: number[]; sources: Record<string, number>; openN: number }>();
  const specialtyBuckets = new Map<string, { amounts: number[]; sources: Record<string, number>; openN: number }>();
  let openN = 0;

  const push = (
    map: Map<string, { amounts: number[]; sources: Record<string, number>; openN: number }>,
    key: string,
    value: number,
    source: string,
    isOpen: boolean,
  ) => {
    const bucket = map.get(key) || { amounts: [], sources: {}, openN: 0 };
    bucket.amounts.push(value);
    bucket.sources[source] = (bucket.sources[source] || 0) + 1;
    if (isOpen) bucket.openN += 1;
    map.set(key, bucket);
  };

  for (const row of rows) {
    const raw = row.salary_min;
    if (raw == null || raw <= 0) continue;
    const cur = (row.salary_currency || "RUB").trim().toUpperCase();
    if (cur && cur !== "RUB" && cur !== "RUR" && cur !== "₽") continue;
    const value = Math.round(raw);
    const source = (row.source || "").trim().toLowerCase() || "other";
    const isOpen = source === "habr" || source === "getmatch";
    amounts.push(value);
    bySource[source] = (bySource[source] || 0) + 1;
    if (isOpen) openN += 1;
    push(gradeBuckets, normalizeGrade(row.grade), value, source, isOpen);
    push(specialtyBuckets, specialtyOf(row), value, source, isOpen);
  }

  const gradeLabels: Record<string, string> = {
    ...Object.fromEntries(LEVELS.map((item) => [item.value, item.label])),
    unknown: "без грейда",
  };

  const orderedGrades = [
    ...GRADE_ORDER.filter((key) => gradeBuckets.has(key)),
    ...[...gradeBuckets.keys()].filter((key) => !(GRADE_ORDER as readonly string[]).includes(key) && key !== "unknown"),
    ...(gradeBuckets.has("unknown") ? ["unknown"] : []),
  ];

  const by_grade = orderedGrades.map((key) => {
    const bucket = gradeBuckets.get(key)!;
    return buildCorridor(bucket.amounts, bucket.sources, bucket.openN, key, gradeLabels[key] || key);
  });

  const by_specialty = [...specialtyBuckets.entries()]
    .sort((a, b) => b[1].amounts.length - a[1].amounts.length || a[0].localeCompare(b[0]))
    .map(([key, bucket]) =>
      buildCorridor(bucket.amounts, bucket.sources, bucket.openN, key, SPECIALTY_LABELS[key] || key),
    );

  return {
    ...buildCorridor(amounts, bySource, openN),
    by_grade,
    by_specialty,
  };
}
