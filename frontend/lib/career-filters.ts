import type { CareerBoard } from "@/lib/types";

export type CareerFilters = {
  company: string;
  search: string;
  formats: string[];
  levels: string[];
  stack: string[];
  cities: string[];
  only_salary: boolean;
  salary_from: number;
};

export const EMPTY_CAREER_FILTERS: CareerFilters = {
  company: "",
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

export function careerFiltersFromParams(params: Record<string, unknown> | undefined): CareerFilters {
  const data = params ?? {};
  return {
    company: String(data.company || data.slug || ""),
    search: String(data.search || ""),
    formats: asList(data.formats || data.format),
    levels: asList(data.levels || data.level),
    stack: asList(data.stack),
    cities: asList(data.cities || data.city),
    only_salary: Boolean(data.only_salary || data.onlySalary),
    salary_from: Number(data.salary_from || data.salaryFrom || data.salary || 0) || 0,
  };
}

export function careerAutoName(filters: CareerFilters, boards: CareerBoard[]): string {
  const board = boards.find((item) => item.slug === filters.company);
  const parts = [board?.name || "сайт компании"];
  if (filters.search.trim()) parts.push(filters.search.trim());
  if (filters.stack.length >= 8) parts.push("весь IT");
  else parts.push(...filters.stack.slice(0, 3));
  return [...new Set(parts)].slice(0, 5).join(" · ");
}

export function careerSummarize(filters: CareerFilters, boards: CareerBoard[]): string {
  const board = boards.find((item) => item.slug === filters.company);
  if (!board) return "компанию не выбрали";
  const bits = [board.name, filters.search.trim(), ...filters.stack, ...filters.formats, ...filters.levels].filter(
    Boolean,
  );
  return [...new Set(bits)].join(" · ");
}
