export const HABR_QUALIFICATIONS = [
  { value: "1", label: "intern" },
  { value: "3", label: "junior" },
  { value: "4", label: "middle" },
  { value: "5", label: "senior" },
  { value: "6", label: "lead" },
] as const;

export const HABR_SPECIALIZATIONS = [
  { value: "2", label: "Backend" },
  { value: "3", label: "Frontend" },
  { value: "4", label: "Fullstack" },
  { value: "5", label: "Mobile" },
  { value: "10", label: "QA Auto" },
  { value: "12", label: "QA Manual" },
  { value: "22", label: "DevOps" },
  { value: "41", label: "Системный аналитик" },
  { value: "43", label: "Data Analyst" },
  { value: "44", label: "Data Scientist" },
  { value: "76", label: "Data Engineer" },
  { value: "73", label: "Архитектор" },
  { value: "7", label: "Embedded" },
] as const;

export type HabrFilters = {
  search: string;
  remote: boolean;
  qid: string;
  s: string[];
  with_salary: boolean;
  salary: number;
};

export const EMPTY_HABR_FILTERS: HabrFilters = {
  search: "",
  remote: false,
  qid: "",
  s: [],
  with_salary: false,
  salary: 0,
};

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value) return [value];
  return [];
}

export function habrFiltersFromParams(params: Record<string, unknown> | undefined): HabrFilters {
  const data = params ?? {};
  const salary = Number(data.salary || 0);
  return {
    search: String(data.search || data.q || ""),
    remote: Boolean(data.remote),
    qid: String(data.qid || ""),
    s: asList(data.s || data.specializations),
    with_salary: Boolean(data.with_salary),
    salary: Number.isFinite(salary) && salary > 0 ? salary : 0,
  };
}

const SPEC_LABELS = Object.fromEntries(HABR_SPECIALIZATIONS.map((item) => [item.value, item.label]));
const GRADE_LABELS = Object.fromEntries(HABR_QUALIFICATIONS.map((item) => [item.value, item.label]));

export function habrAutoName(filters: HabrFilters): string {
  const parts: string[] = [];
  if (filters.search.trim()) parts.push(filters.search.trim());
  if (filters.s.length >= 8) parts.push("весь IT");
  else for (const spec of filters.s) parts.push(SPEC_LABELS[spec] ?? spec);
  if (filters.remote) parts.push("удалённо");
  if (filters.qid) parts.push(GRADE_LABELS[filters.qid] ?? filters.qid);
  if (filters.salary) parts.push(`от ${filters.salary}`);
  return [...new Set(parts)].slice(0, 5).join(" · ") || "Habr Career поиск";
}

export function habrSummarize(filters: HabrFilters): string {
  const bits = [
    filters.search.trim(),
    ...filters.s.map((spec) => SPEC_LABELS[spec] ?? spec),
    filters.remote ? "удалённо" : "",
    filters.qid ? (GRADE_LABELS[filters.qid] ?? filters.qid) : "",
    filters.with_salary ? "с зарплатой" : "",
    filters.salary ? `от ${filters.salary}` : "",
  ].filter(Boolean);
  return [...new Set(bits)].join(" · ") || "без фильтров";
}
