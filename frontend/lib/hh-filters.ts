export const HH_AREAS = [
  { value: "1", label: "Москва" },
  { value: "2", label: "Санкт-Петербург" },
  { value: "113", label: "Россия" },
  { value: "3", label: "Екатеринбург" },
  { value: "4", label: "Новосибирск" },
  { value: "88", label: "Казань" },
  { value: "66", label: "Нижний Новгород" },
] as const;

export const HH_EXPERIENCE = [
  { value: "noExperience", label: "без опыта" },
  { value: "between1And3", label: "1–3 года" },
  { value: "between3And6", label: "3–6 лет" },
  { value: "moreThan6", label: "6+ лет" },
] as const;

export const HH_SCHEDULE = [
  { value: "remote", label: "удалённо" },
  { value: "fullDay", label: "полный день" },
  { value: "flexible", label: "гибкий" },
  { value: "shift", label: "смены" },
  { value: "flyInFlyOut", label: "вахта" },
] as const;

export const HH_EMPLOYMENT = [
  { value: "full", label: "полная" },
  { value: "part", label: "частичная" },
  { value: "project", label: "проект" },
  { value: "probation", label: "стажировка" },
] as const;

export const HH_SORTS = [
  { value: "publication_time", label: "сначала новые" },
  { value: "salary_desc", label: "больше денег" },
  { value: "relevance", label: "по соответствию" },
] as const;

export const HH_PERIODS = [
  { value: "", label: "за всё время" },
  { value: "1", label: "за сутки" },
  { value: "3", label: "за 3 дня" },
  { value: "7", label: "за неделю" },
  { value: "30", label: "за месяц" },
] as const;

export type HhFilters = {
  search: string;
  area: string[];
  experience: string[];
  schedule: string[];
  employment: string[];
  order_by: string;
  search_period: string;
  only_with_salary: boolean;
  headed: boolean;
};

export const EMPTY_HH_FILTERS: HhFilters = {
  search: "",
  area: ["1"],
  experience: [],
  schedule: [],
  employment: [],
  order_by: "publication_time",
  search_period: "",
  only_with_salary: false,
  headed: false,
};

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value) return [value];
  return [];
}

export function hhFiltersFromParams(params: Record<string, unknown> | undefined): HhFilters {
  const data = params ?? {};
  return {
    search: String(data.search || data.text || ""),
    area: asList(data.area).length ? asList(data.area) : ["1"],
    experience: asList(data.experience),
    schedule: asList(data.schedule),
    employment: asList(data.employment),
    order_by: String(data.order_by || "publication_time"),
    search_period: String(data.search_period ?? ""),
    only_with_salary: Boolean(data.only_with_salary),
    headed: Boolean(data.headed),
  };
}

const LABELS: Record<string, string> = Object.fromEntries([
  ...HH_AREAS,
  ...HH_EXPERIENCE,
  ...HH_SCHEDULE,
  ...HH_EMPLOYMENT,
].map((item) => [item.value, item.label]));

export function hhAutoName(filters: HhFilters): string {
  const parts: string[] = [];
  if (filters.search.trim()) parts.push(filters.search.trim());
  for (const area of filters.area) parts.push(LABELS[area] ?? area);
  for (const item of filters.schedule) parts.push(LABELS[item] ?? item);
  for (const item of filters.experience) parts.push(LABELS[item] ?? item);
  return [...new Set(parts)].slice(0, 5).join(" · ") || "hh.ru поиск";
}

export function hhSummarize(filters: HhFilters): string {
  const bits = [
    filters.search.trim(),
    ...filters.area.map((v) => LABELS[v] ?? v),
    ...filters.experience.map((v) => LABELS[v] ?? v),
    ...filters.schedule.map((v) => LABELS[v] ?? v),
    ...filters.employment.map((v) => LABELS[v] ?? v),
    filters.only_with_salary ? "с зарплатой" : "",
    filters.headed ? "Chrome на экране" : "",
  ].filter(Boolean);
  return [...new Set(bits)].join(" · ") || "без фильтров";
}
