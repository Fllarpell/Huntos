export const CATEGORIES = [
  { value: "development", label: "Разработка" },
  { value: "devops", label: "DevOps" },
  { value: "qa", label: "Тестирование" },
  { value: "analytics", label: "Аналитика" },
  { value: "design", label: "Дизайн" },
  { value: "management", label: "Менеджмент" },
  { value: "marketing", label: "Маркетинг" },
  { value: "sales", label: "Продажи" },
  { value: "finance", label: "Финансы" },
  { value: "recruiting", label: "Рекрутинг" },
] as const;

export const SUBCATEGORIES = [
  { value: "ml_ai", label: "ML/AI" },
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "backend", label: "Backend" },
  { value: "go", label: "Go" },
  { value: "data_engineer", label: "Data Engineer" },
  { value: "frontend", label: "Frontend" },
  { value: "fullstack", label: "Fullstack" },
  { value: "netc", label: ".NET/C#" },
  { value: "cpp", label: "C++" },
  { value: "php", label: "PHP" },
  { value: "nodejs", label: "Node.js" },
  { value: "kotlin", label: "Kotlin" },
  { value: "rust", label: "Rust" },
  { value: "mobile", label: "Mobile" },
  { value: "android", label: "Android" },
  { value: "ios", label: "iOS" },
  { value: "onec", label: "1C" },
  { value: "erp_crm", label: "ERP / CRM" },
] as const;

export const FORMATS = [
  { value: "удалённо", label: "удалённо" },
  { value: "офис", label: "офис" },
  { value: "гибрид", label: "гибрид" },
  { value: "удалённо по РФ", label: "удалённо по РФ" },
] as const;

export const LEVELS = [
  { value: "intern", label: "intern" },
  { value: "junior", label: "junior" },
  { value: "middle", label: "middle" },
  { value: "senior", label: "senior" },
  { value: "lead", label: "lead" },
  { value: "head", label: "head" },
] as const;

export const ENGLISH = [
  { value: "english", label: "нужен английский" },
  { value: "no_english", label: "не нужен английский" },
] as const;

export const CONTACTS = [
  { value: "direct_contact", label: "прямой контакт" },
] as const;

export const SORTS = [
  { value: "date", label: "сначала новые" },
  { value: "salary_desc", label: "больше денег" },
] as const;

export type HireHiFilters = {
  category: string;
  search: string;
  sort: string;
  format: string[];
  level: string[];
  subcategory: string[];
  english: string[];
  direct_contact: string[];
};

export const EMPTY_FILTERS: HireHiFilters = {
  category: "development",
  search: "",
  sort: "date",
  format: [],
  level: [],
  subcategory: [],
  english: [],
  direct_contact: [],
};

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value) return [value];
  return [];
}

export function filtersFromParams(params: Record<string, unknown> | undefined): HireHiFilters {
  const data = params ?? {};
  return {
    category: String(data.category || "development"),
    search: String(data.search || ""),
    sort: String(data.sort || "date"),
    format: asList(data.format),
    level: asList(data.level),
    subcategory: asList(data.subcategory),
    english: asList(data.english),
    direct_contact: asList(data.direct_contact),
  };
}

export function autoName(filters: HireHiFilters): string {
  const subLabels = Object.fromEntries(SUBCATEGORIES.map((s) => [s.value, s.label]));
  const parts: string[] = [];
  const search = filters.search.trim();
  if (search) parts.push(search);
  for (const slug of filters.subcategory) {
    const label = subLabels[slug] ?? slug;
    if (label.toLowerCase() !== search.toLowerCase()) parts.push(label);
  }
  parts.push(...filters.format);
  if (filters.level.length) parts.push(filters.level.join(", "));
  if (filters.english.includes("english")) parts.push("EN");
  if (filters.english.includes("no_english")) parts.push("без EN");
  return [...new Set(parts)].slice(0, 5).join(" · ") || "HireHi поиск";
}

export function summarize(filters: HireHiFilters): string {
  const subLabels = Object.fromEntries(SUBCATEGORIES.map((s) => [s.value, s.label]));
  const bits = [
    filters.search.trim(),
    ...filters.subcategory.map((s) => subLabels[s] ?? s),
    ...filters.format,
    ...filters.level,
    ...ENGLISH.filter((e) => filters.english.includes(e.value)).map((e) => e.label),
    ...filters.direct_contact.map(() => "прямой контакт"),
  ].filter(Boolean);
  return [...new Set(bits)].join(" · ") || "без фильтров";
}

export function toggleValue(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}
