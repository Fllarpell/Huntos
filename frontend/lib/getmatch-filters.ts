export const GETMATCH_SPECIALTIES = [
  { value: "python", label: "Python" },
  { value: "golang", label: "Go" },
  { value: "java_scala", label: "Java / Scala" },
  { value: "js_frontend", label: "JS / TS" },
  { value: "js_backend", label: "Node.js" },
  { value: "fullstack", label: "Fullstack" },
  { value: "qa_auto", label: "QA Auto" },
  { value: "qa_manual", label: "QA Manual" },
  { value: "dev_ops", label: "DevOps" },
  { value: "data_science", label: "ML / DS" },
  { value: "android", label: "Android" },
  { value: "ios", label: "iOS" },
  { value: "c_sharp", label: "C#" },
  { value: "php", label: "PHP" },
  { value: "kotlin", label: "Kotlin" },
  { value: "system_analyst", label: "Системный аналитик" },
  { value: "product_management", label: "Product" },
] as const;

export const GETMATCH_LOCATIONS = [
  { value: "remote", label: "удалённо" },
  { value: "moscow", label: "Москва" },
  { value: "saint_petersburg", label: "Санкт-Петербург" },
] as const;

export const GETMATCH_LEVELS = [
  { value: "junior", label: "junior" },
  { value: "middle", label: "middle" },
  { value: "senior", label: "senior" },
  { value: "lead", label: "lead" },
  { value: "c-level", label: "c-level" },
] as const;

export const GETMATCH_SALARIES = [
  { value: "0", label: "любая" },
  { value: "150000", label: "от 150 000" },
  { value: "200000", label: "от 200 000" },
  { value: "250000", label: "от 250 000" },
  { value: "350000", label: "от 350 000" },
] as const;

export type GetMatchFilters = {
  search: string;
  specialty: string;
  specialties?: string[];
  location: string;
  level: string[];
  salary: number;
};

export const EMPTY_GETMATCH_FILTERS: GetMatchFilters = {
  search: "",
  specialty: "",
  specialties: [],
  location: "",
  level: [],
  salary: 0,
};

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value) return [value];
  return [];
}

export function getmatchFiltersFromParams(params: Record<string, unknown> | undefined): GetMatchFilters {
  const data = params ?? {};
  const salary = Number(data.salary || data.salary_from || 0);
  const specialties = asList(data.specialties || data.specialty || data.sp);
  return {
    search: String(data.search || data.q || ""),
    specialty: specialties[0] || String(data.specialty || data.sp || ""),
    specialties,
    location: String(data.location || data.l || ""),
    level: asList(data.level || data.g),
    salary: Number.isFinite(salary) && salary > 0 ? salary : 0,
  };
}

const LABELS: Record<string, string> = Object.fromEntries([
  ...GETMATCH_SPECIALTIES,
  ...GETMATCH_LOCATIONS,
].map((item) => [item.value, item.label]));

export function getmatchAutoName(filters: GetMatchFilters): string {
  const parts: string[] = [];
  if (filters.search.trim()) parts.push(filters.search.trim());
  const specialties = filters.specialties?.length ? filters.specialties : filters.specialty ? [filters.specialty] : [];
  if (specialties.length >= 8) parts.push("все специальности");
  else if (specialties.length > 1) parts.push(`${specialties.length} специальностей`);
  else if (specialties[0]) parts.push(LABELS[specialties[0]] ?? specialties[0]);
  if (filters.location) parts.push(LABELS[filters.location] ?? filters.location);
  parts.push(...filters.level);
  if (filters.salary) parts.push(`от ${filters.salary}`);
  return [...new Set(parts)].slice(0, 5).join(" · ") || "GetMatch поиск";
}

export function getmatchSummarize(filters: GetMatchFilters): string {
  const bits = [
    filters.search.trim(),
    filters.specialty ? (LABELS[filters.specialty] ?? filters.specialty) : "",
    filters.location ? (LABELS[filters.location] ?? filters.location) : "",
    ...filters.level,
    filters.salary ? `от ${filters.salary}` : "",
  ].filter(Boolean);
  return [...new Set(bits)].join(" · ") || "без фильтров";
}
