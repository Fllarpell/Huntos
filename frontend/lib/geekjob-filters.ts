export type GeekJobFilters = {
  search: string;
  formats: string[];
  levels: string[];
  stack: string[];
  cities: string[];
  only_salary: boolean;
  salary_from: number;
};

export const EMPTY_GEEKJOB_FILTERS: GeekJobFilters = {
  search: "",
  formats: [],
  levels: [],
  stack: [],
  cities: [],
  only_salary: false,
  salary_from: 0,
};

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value) return [value];
  return [];
}

export function geekjobFiltersFromParams(params: Record<string, unknown> | undefined): GeekJobFilters {
  const data = params ?? {};
  return {
    search: String(data.search || data.q || data.qs || ""),
    formats: asList(data.formats || data.format),
    levels: asList(data.levels || data.level),
    stack: asList(data.stack),
    cities: asList(data.cities || data.city),
    only_salary: Boolean(data.only_salary || data.onlySalary),
    salary_from: Number(data.salary_from || data.salaryFrom || data.salary || 0) || 0,
  };
}

export function geekjobAutoName(filters: GeekJobFilters): string {
  const parts: string[] = [];
  if (filters.search.trim()) parts.push(filters.search.trim());
  if (filters.stack.length >= 8) parts.push("весь IT");
  else parts.push(...filters.stack.slice(0, 3));
  if (filters.formats.includes("remote")) parts.push("удалённо");
  return [...new Set(parts)].slice(0, 5).join(" · ") || "GeekJob поиск";
}

export function geekjobSummarize(filters: GeekJobFilters): string {
  const bits = [filters.search.trim(), ...filters.stack, ...filters.formats, ...filters.levels].filter(Boolean);
  return [...new Set(bits)].join(" · ") || "без фильтров";
}
