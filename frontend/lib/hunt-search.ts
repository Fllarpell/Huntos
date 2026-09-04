import {
  EMPTY_FILTERS,
  autoName,
  filtersFromParams,
  type HireHiFilters,
} from "@/lib/hirehi-filters";
import {
  EMPTY_HH_FILTERS,
  hhAutoName,
  hhFiltersFromParams,
  type HhFilters,
} from "@/lib/hh-filters";
import {
  EMPTY_HABR_FILTERS,
  habrAutoName,
  habrFiltersFromParams,
  type HabrFilters,
} from "@/lib/habr-filters";
import {
  EMPTY_GETMATCH_FILTERS,
  getmatchAutoName,
  getmatchFiltersFromParams,
  type GetMatchFilters,
} from "@/lib/getmatch-filters";
import {
  careerAutoName,
  careerFiltersFromParams,
} from "@/lib/career-filters";
import {
  geekjobAutoName,
  geekjobFiltersFromParams,
} from "@/lib/geekjob-filters";
import type { CareerBoard, ScraperConfig } from "@/lib/types";
import { SEARCH_CITIES, RUSSIA_AREA } from "@/lib/hunt-cities";

export { SEARCH_CITIES } from "@/lib/hunt-cities";

export type HuntSearch = {
  search: string;
  formats: string[];
  levels: string[];
  stack: string[];
  cities: string[];
  onlySalary: boolean;
  salaryFrom: number;
  intervalMinutes: number;
  hirehiCategory: string;
  hirehiEnglish: string[];
  hirehiContacts: string[];
  hirehiSort: string;
  hhEmployment: string[];
  hhOrderBy: string;
  hhPeriod: string;
  hhHeaded: boolean;
};

export const EMPTY_HUNT_SEARCH: HuntSearch = {
  search: "",
  formats: [],
  levels: [],
  stack: [],
  cities: [RUSSIA_AREA],
  onlySalary: false,
  salaryFrom: 0,
  intervalMinutes: 60,
  hirehiCategory: "development",
  hirehiEnglish: [],
  hirehiContacts: [],
  hirehiSort: "date",
  hhEmployment: [],
  hhOrderBy: "publication_time",
  hhPeriod: "",
  hhHeaded: false,
};

export const SEARCH_FORMATS = [
  { value: "remote", label: "удалённо" },
  { value: "office", label: "офис" },
  { value: "hybrid", label: "гибрид" },
] as const;

export const SEARCH_LEVELS = [
  { value: "intern", label: "intern" },
  { value: "junior", label: "junior" },
  { value: "middle", label: "middle" },
  { value: "senior", label: "senior" },
  { value: "lead", label: "lead" },
  { value: "head", label: "head" },
] as const;

export const SEARCH_STACK_GROUPS = [
  {
    label: "Языки",
    items: [
      { value: "python", label: "Python" },
      { value: "go", label: "Go" },
      { value: "java", label: "Java" },
      { value: "csharp", label: "C# / .NET" },
      { value: "cpp", label: "C++" },
      { value: "php", label: "PHP" },
      { value: "rust", label: "Rust" },
      { value: "kotlin", label: "Kotlin" },
      { value: "scala", label: "Scala" },
      { value: "ruby", label: "Ruby" },
      { value: "nodejs", label: "Node.js" },
      { value: "onec", label: "1C" },
    ],
  },
  {
    label: "Роли",
    items: [
      { value: "backend", label: "Backend" },
      { value: "frontend", label: "Frontend" },
      { value: "fullstack", label: "Fullstack" },
      { value: "mobile", label: "Mobile" },
      { value: "android", label: "Android" },
      { value: "ios", label: "iOS" },
    ],
  },
  {
    label: "Качество и эксплуатация",
    items: [
      { value: "qa", label: "QA" },
      { value: "devops", label: "DevOps" },
      { value: "sre", label: "SRE" },
      { value: "admin", label: "Admin" },
      { value: "security", label: "Security" },
      { value: "embedded", label: "Embedded" },
    ],
  },
  {
    label: "Данные и продукт",
    items: [
      { value: "ml", label: "ML / AI" },
      { value: "data", label: "Data Engineer" },
      { value: "analytics", label: "Analytics" },
      { value: "sysanalyst", label: "Системный аналитик" },
      { value: "architect", label: "Архитектор" },
      { value: "product", label: "Product" },
      { value: "design", label: "Design / UX" },
    ],
  },
] as const;

export const SEARCH_STACK = SEARCH_STACK_GROUPS.flatMap((group) => [...group.items]);

export const SEARCH_SALARIES = [
  { value: 0, label: "любая" },
  { value: 150000, label: "от 150 000" },
  { value: 200000, label: "от 200 000" },
  { value: 250000, label: "от 250 000" },
  { value: 350000, label: "от 350 000" },
] as const;

const HIREHI_STACK: Record<string, string> = {
  python: "python",
  go: "go",
  java: "java",
  backend: "backend",
  frontend: "frontend",
  fullstack: "fullstack",
  nodejs: "nodejs",
  mobile: "mobile",
  android: "android",
  ios: "ios",
  ml: "ml_ai",
  data: "data_engineer",
  csharp: "netc",
  cpp: "cpp",
  php: "php",
  rust: "rust",
  kotlin: "kotlin",
  onec: "onec",
};

const HIREHI_FORMAT: Record<string, string> = {
  remote: "удалённо",
  office: "офис",
  hybrid: "гибрид",
};

const HH_FORMAT: Record<string, string> = {
  remote: "remote",
  office: "fullDay",
  hybrid: "flexible",
};

const HH_LEVEL: Record<string, string> = {
  intern: "noExperience",
  junior: "between1And3",
  middle: "between3And6",
  senior: "between3And6",
  lead: "moreThan6",
  head: "moreThan6",
};

const HABR_STACK: Record<string, string[]> = {
  backend: ["2"],
  frontend: ["3"],
  fullstack: ["4"],
  mobile: ["5"],
  android: ["5"],
  ios: ["5"],
  qa: ["10", "12"],
  devops: ["22"],
  sre: ["22"],
  ml: ["44"],
  data: ["76"],
  analytics: ["43"],
  sysanalyst: ["41"],
  architect: ["73"],
  embedded: ["7"],
};

const HABR_LEVEL: Record<string, string> = {
  intern: "1",
  junior: "3",
  middle: "4",
  senior: "5",
  lead: "6",
  head: "6",
};

const GETMATCH_STACK: Record<string, string | string[]> = {
  python: "python",
  go: "golang",
  java: "java_scala",
  scala: "java_scala",
  frontend: "js_frontend",
  nodejs: "js_backend",
  fullstack: "fullstack",
  qa: ["qa_auto", "qa_manual"],
  devops: "dev_ops",
  sre: "dev_ops",
  ml: "data_science",
  android: "android",
  ios: "ios",
  csharp: "c_sharp",
  php: "php",
  kotlin: "kotlin",
  sysanalyst: "system_analyst",
  product: "product_management",
};

const GETMATCH_CITY: Record<string, string> = {
  "1": "moscow",
  "2": "saint_petersburg",
};

function unique(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

export function toHireHi(draft: HuntSearch): HireHiFilters {
  const only = (keys: string[]) =>
    draft.stack.length > 0 && draft.stack.every((item) => keys.includes(item));
  const category = only(["qa"])
    ? "qa"
    : only(["devops", "sre", "admin"])
      ? "devops"
      : only(["analytics", "sysanalyst"])
        ? "analytics"
        : only(["design"])
          ? "design"
          : only(["product"])
            ? "management"
            : draft.hirehiCategory || "development";
  const subcategory = unique(draft.stack.map((item) => HIREHI_STACK[item]).filter(Boolean));
  // Wide hunt: don't pin HireHi to a handful of chips — take the whole category feed.
  const wide = draft.stack.length >= 8 || subcategory.length >= 10;
  return {
    ...EMPTY_FILTERS,
    category,
    search: draft.search,
    sort: draft.hirehiSort || "date",
    format: unique(draft.formats.map((item) => HIREHI_FORMAT[item]).filter(Boolean)),
    level: draft.levels.filter((item) => SEARCH_LEVELS.some((row) => row.value === item)),
    subcategory: wide ? [] : subcategory,
    english: draft.hirehiEnglish,
    direct_contact: draft.hirehiContacts,
  };
}

export function toHh(draft: HuntSearch): HhFilters {
  const experience = unique(draft.levels.map((item) => HH_LEVEL[item]).filter(Boolean));
  const schedule = unique(draft.formats.map((item) => HH_FORMAT[item]).filter(Boolean));
  const allExp = experience.length >= 4;
  const allSchedules = ["remote", "fullDay", "flexible"].every((item) => schedule.includes(item));
  return {
    ...EMPTY_HH_FILTERS,
    search: draft.search,
    area: draft.cities.length ? draft.cities : [RUSSIA_AREA],
    experience: allExp ? [] : experience,
    schedule: allSchedules ? [] : schedule,
    employment: draft.hhEmployment,
    order_by: draft.hhOrderBy || "publication_time",
    search_period: draft.hhPeriod,
    only_with_salary: draft.onlySalary,
    headed: draft.hhHeaded,
  };
}

export function toHabr(draft: HuntSearch): HabrFilters {
  const mappedLevels = unique(draft.levels.map((item) => HABR_LEVEL[item]).filter(Boolean));
  return {
    ...EMPTY_HABR_FILTERS,
    search: draft.search,
    remote: draft.formats.includes("remote"),
    qid: mappedLevels.length === 1 ? mappedLevels[0] : "",
    s: unique(draft.stack.flatMap((item) => HABR_STACK[item] || [])),
    with_salary: draft.onlySalary,
    salary: draft.salaryFrom,
  };
}

export function toGetmatch(draft: HuntSearch): GetMatchFilters {
  const specialties = unique(
    draft.stack.flatMap((item) => {
      const mapped = GETMATCH_STACK[item];
      if (!mapped) return [];
      return Array.isArray(mapped) ? mapped : [mapped];
    }),
  );
  const location = draft.formats.includes("remote")
    ? "remote"
    : draft.cities.map((item) => GETMATCH_CITY[item]).find(Boolean) || "";
  const allowed = new Set(["junior", "middle", "senior", "lead"]);
  return {
    ...EMPTY_GETMATCH_FILTERS,
    search: draft.search,
    specialty: specialties[0] || "",
    specialties,
    location,
    level: draft.levels.filter((item) => allowed.has(item)),
    salary: draft.salaryFrom,
  };
}

export function toCareer(draft: HuntSearch, company: string) {
  return {
    company,
    search: draft.search,
    formats: draft.formats,
    levels: draft.levels,
    stack: draft.stack,
    cities: draft.cities,
    only_salary: draft.onlySalary,
    salary_from: draft.salaryFrom,
  };
}

export function toGeekjob(draft: HuntSearch) {
  return {
    search: draft.search,
    formats: draft.formats,
    levels: draft.levels,
    stack: draft.stack,
    cities: draft.cities,
    only_salary: draft.onlySalary,
    salary_from: draft.salaryFrom,
  };
}

export function maxPagesForSource(source: string): number {
  if (source === "hh" || source === "habr" || source === "geekjob") return 40;
  if (source === "getmatch") return 20;
  return 5;
}

export function payloadForPick(key: string, draft: HuntSearch, boards: CareerBoard[]) {
  if (key.startsWith("career:")) {
    const company = key.slice("career:".length);
    const career = toCareer(draft, company);
    return {
      name: careerAutoName(career, boards),
      source: "career" as const,
      enabled: true,
      interval_minutes: Math.max(draft.intervalMinutes, 60),
      max_pages: maxPagesForSource("career"),
      query_params: career,
    };
  }
  if (key === "hh") {
    const query_params = toHh(draft);
    return {
      name: hhAutoName(query_params),
      source: "hh" as const,
      enabled: true,
      interval_minutes: Math.max(draft.intervalMinutes, 180),
      max_pages: maxPagesForSource("hh"),
      query_params,
    };
  }
  if (key === "habr") {
    const query_params = toHabr(draft);
    return {
      name: habrAutoName(query_params),
      source: "habr" as const,
      enabled: true,
      interval_minutes: Math.max(draft.intervalMinutes, 60),
      max_pages: maxPagesForSource("habr"),
      query_params,
    };
  }
  if (key === "getmatch") {
    const query_params = toGetmatch(draft);
    return {
      name: getmatchAutoName(query_params),
      source: "getmatch" as const,
      enabled: true,
      interval_minutes: Math.max(draft.intervalMinutes, 180),
      max_pages: maxPagesForSource("getmatch"),
      query_params,
    };
  }
  if (key === "geekjob") {
    const query_params = toGeekjob(draft);
    return {
      name: geekjobAutoName(query_params),
      source: "geekjob" as const,
      enabled: true,
      interval_minutes: Math.max(draft.intervalMinutes, 60),
      max_pages: maxPagesForSource("geekjob"),
      query_params,
    };
  }
  const query_params = toHireHi(draft);
  return {
    name: autoName(query_params),
    source: "hirehi" as const,
    enabled: true,
    interval_minutes: Math.max(draft.intervalMinutes, 60),
    max_pages: maxPagesForSource("hirehi"),
    query_params,
  };
}

const HIREHI_STACK_BACK: Record<string, string> = Object.fromEntries(
  Object.entries(HIREHI_STACK).map(([key, value]) => [value, key]),
);
const HIREHI_FORMAT_BACK: Record<string, string> = Object.fromEntries(
  Object.entries(HIREHI_FORMAT).map(([key, value]) => [value, key]),
);
const HH_FORMAT_BACK: Record<string, string> = Object.fromEntries(
  Object.entries(HH_FORMAT).map(([key, value]) => [value, key]),
);
const HH_LEVEL_BACK: Record<string, string> = {
  noExperience: "intern",
  between1And3: "junior",
  between3And6: "middle",
  moreThan6: "senior",
};
const HABR_STACK_BACK: Record<string, string> = {
  "2": "backend",
  "3": "frontend",
  "4": "fullstack",
  "5": "mobile",
  "10": "qa",
  "12": "qa",
  "22": "devops",
  "44": "ml",
  "76": "data",
  "43": "analytics",
  "41": "sysanalyst",
  "73": "architect",
  "7": "embedded",
};
const HABR_LEVEL_BACK: Record<string, string> = {
  "1": "intern",
  "3": "junior",
  "4": "middle",
  "5": "senior",
  "6": "lead",
};
const GETMATCH_STACK_BACK: Record<string, string> = Object.fromEntries(
  Object.entries(GETMATCH_STACK).flatMap(([key, value]) =>
    (Array.isArray(value) ? value : [value]).map((item) => [item, key]),
  ),
);
const GETMATCH_CITY_BACK: Record<string, string> = Object.fromEntries(
  Object.entries(GETMATCH_CITY).map(([key, value]) => [value, key]),
);

export function draftFromConfig(config: ScraperConfig): HuntSearch {
  const base = {
    ...EMPTY_HUNT_SEARCH,
    intervalMinutes: Math.max(30, config.interval_minutes || 60),
  };
  if (config.source === "hh") {
    const hh = hhFiltersFromParams(config.query_params);
    return {
      ...base,
      search: hh.search,
      formats: unique(hh.schedule.map((item) => HH_FORMAT_BACK[item]).filter(Boolean)),
      levels: unique(hh.experience.map((item) => HH_LEVEL_BACK[item]).filter(Boolean)),
      cities: hh.area.length ? hh.area : [RUSSIA_AREA],
      onlySalary: hh.only_with_salary,
      hhEmployment: hh.employment,
      hhOrderBy: hh.order_by,
      hhPeriod: hh.search_period,
      hhHeaded: hh.headed,
    };
  }
  if (config.source === "habr") {
    const habr = habrFiltersFromParams(config.query_params);
    return {
      ...base,
      search: habr.search,
      formats: habr.remote ? ["remote"] : [],
      levels: habr.qid && HABR_LEVEL_BACK[habr.qid] ? [HABR_LEVEL_BACK[habr.qid]] : [],
      stack: unique(habr.s.map((item) => HABR_STACK_BACK[item]).filter(Boolean)),
      onlySalary: habr.with_salary,
      salaryFrom: habr.salary,
    };
  }
  if (config.source === "getmatch") {
    const gm = getmatchFiltersFromParams(config.query_params);
    const specialties = gm.specialties?.length ? gm.specialties : gm.specialty ? [gm.specialty] : [];
    return {
      ...base,
      search: gm.search,
      formats: gm.location === "remote" ? ["remote"] : [],
      levels: gm.level,
      stack: unique(specialties.map((item) => GETMATCH_STACK_BACK[item]).filter(Boolean)),
      cities: gm.location && gm.location !== "remote" && GETMATCH_CITY_BACK[gm.location]
        ? [GETMATCH_CITY_BACK[gm.location]]
        : base.cities,
      salaryFrom: gm.salary,
    };
  }
  if (config.source === "geekjob") {
    const geekjob = geekjobFiltersFromParams(config.query_params);
    return {
      ...base,
      search: geekjob.search,
      formats: geekjob.formats,
      levels: geekjob.levels,
      stack: geekjob.stack,
      cities: geekjob.cities.length ? geekjob.cities : base.cities,
      onlySalary: geekjob.only_salary,
      salaryFrom: geekjob.salary_from,
    };
  }
  if (config.source === "career") {
    const career = careerFiltersFromParams(config.query_params);
    return {
      ...base,
      search: career.search,
      formats: career.formats,
      levels: career.levels,
      stack: career.stack,
      cities: career.cities.length ? career.cities : base.cities,
      onlySalary: career.only_salary,
      salaryFrom: career.salary_from,
    };
  }
  const hirehi = filtersFromParams(config.query_params);
  return {
    ...base,
    search: hirehi.search,
    formats: unique(hirehi.format.map((item) => HIREHI_FORMAT_BACK[item]).filter(Boolean)),
    levels: hirehi.level,
    stack: unique(hirehi.subcategory.map((item) => HIREHI_STACK_BACK[item]).filter(Boolean)),
    hirehiCategory: hirehi.category,
    hirehiEnglish: hirehi.english,
    hirehiContacts: hirehi.direct_contact,
    hirehiSort: hirehi.sort,
  };
}

export function appliesHint(key: string, draft: HuntSearch): string {
  const bits: string[] = [];
  if (draft.search.trim()) bits.push(draft.search.trim());
  if (key.startsWith("career:")) {
    if (draft.stack.length >= 8) bits.push("весь IT");
    else bits.push(...draft.stack.map((item) => SEARCH_STACK.find((row) => row.value === item)?.label || item));
    bits.push(...draft.formats.map((item) => SEARCH_FORMATS.find((row) => row.value === item)?.label || item));
    bits.push(...draft.levels);
    bits.push(...draft.cities.map((id) => SEARCH_CITIES.find((row) => row.value === id)?.label || id));
    if (draft.onlySalary) bits.push("с зарплатой");
    if (draft.salaryFrom) bits.push(`от ${draft.salaryFrom}`);
    return bits.filter(Boolean).join(" · ") || "IT-лента, фильтры из общего поиска";
  }
  if (key === "hh") {
    bits.push(...draft.cities.map((id) => SEARCH_CITIES.find((row) => row.value === id)?.label || id));
    if (draft.stack.length >= 8 || !draft.stack.length) bits.push("весь IT");
    else bits.push(...draft.stack.map((item) => SEARCH_STACK.find((row) => row.value === item)?.label || item));
    if (draft.formats.length && draft.formats.length < 3) {
      bits.push(...draft.formats.map((item) => SEARCH_FORMATS.find((row) => row.value === item)?.label || item));
    }
    if (draft.levels.length && draft.levels.length < 5) bits.push(...draft.levels);
    if (draft.onlySalary) bits.push("с зарплатой");
    return bits.filter(Boolean).join(" · ") || "весь IT по России";
  }
  if (key === "habr") {
    if (draft.formats.includes("remote")) bits.push("удалённо");
    bits.push(...draft.stack.map((item) => SEARCH_STACK.find((row) => row.value === item)?.label || item));
    if (draft.levels.length === 1) bits.push(draft.levels[0]);
    if (draft.onlySalary) bits.push("с зарплатой");
    if (draft.salaryFrom) bits.push(`от ${draft.salaryFrom}`);
    return bits.filter(Boolean).join(" · ") || "без фильтров";
  }
  if (key === "getmatch") {
    const labels = draft.stack.map((item) => SEARCH_STACK.find((row) => row.value === item)?.label || item);
    if (labels.length >= 8) bits.push("все специальности");
    else if (labels.length > 1) bits.push(`${labels.length} специальностей`);
    else bits.push(...labels);
    bits.push(
      draft.formats.includes("remote")
        ? "удалённо"
        : draft.cities[0] === "2"
          ? "Санкт-Петербург"
          : draft.cities[0] === "1"
            ? "Москва"
            : draft.cities[0] === RUSSIA_AREA
              ? "Россия"
              : "",
    );
    bits.push(...draft.levels.filter((item) => ["junior", "middle", "senior", "lead"].includes(item)));
    if (draft.salaryFrom) bits.push(`от ${draft.salaryFrom}`);
    return bits.filter(Boolean).join(" · ") || "без фильтров";
  }
  if (key === "geekjob") {
    bits.push(...draft.stack.map((item) => SEARCH_STACK.find((row) => row.value === item)?.label || item));
    bits.push(...draft.formats.map((item) => SEARCH_FORMATS.find((row) => row.value === item)?.label || item));
    bits.push(...draft.levels);
    if (draft.onlySalary) bits.push("с зарплатой");
    if (draft.salaryFrom) bits.push(`от ${draft.salaryFrom}`);
    return bits.filter(Boolean).join(" · ") || "IT-лента GeekJob, фильтры из общего поиска";
  }
  bits.push(...draft.stack.map((item) => SEARCH_STACK.find((row) => row.value === item)?.label || item));
  bits.push(...draft.formats.map((item) => SEARCH_FORMATS.find((row) => row.value === item)?.label || item));
  bits.push(...draft.levels);
  return bits.filter(Boolean).join(" · ") || "без фильтров";
}

export function pickKeyFromConfig(config: { source: string; query_params?: Record<string, unknown> }): string {
  if (config.source === "career") {
    return `career:${String(config.query_params?.company || "")}`;
  }
  return config.source;
}

function canonicalQuery(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value
      .map(canonicalQuery)
      .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      const item = (value as Record<string, unknown>)[key];
      if (item == null || item === "" || item === false) continue;
      if (Array.isArray(item) && item.length === 0) continue;
      out[key] = canonicalQuery(item);
    }
    return out;
  }
  if (typeof value === "string") return value.trim().toLowerCase();
  return value;
}

export function queryParamsEqual(
  left: Record<string, unknown> | undefined,
  right: Record<string, unknown> | undefined,
): boolean {
  return JSON.stringify(canonicalQuery(left ?? {})) === JSON.stringify(canonicalQuery(right ?? {}));
}

export function configCoversPick(
  config: ScraperConfig,
  key: string,
  draft: HuntSearch,
  boards: CareerBoard[],
): boolean {
  if (pickKeyFromConfig(config) !== key) return false;
  const saved = payloadForPick(key, draftFromConfig(config), boards).query_params as Record<string, unknown>;
  const next = payloadForPick(key, draft, boards).query_params as Record<string, unknown>;
  return queryParamsEqual(saved, next);
}
