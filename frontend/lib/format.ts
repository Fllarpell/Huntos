export function matchTone(score: number | null): "high" | "mid" | "low" | "none" {
  if (score == null) return "none";
  if (score >= 80) return "high";
  if (score >= 50) return "mid";
  return "low";
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diff = Date.now() - date.getTime();
  const min = Math.round(diff / 60000);
  if (min < 1) return "только что";
  if (min < 60) return `${min} мин назад`;
  const hours = Math.round(min / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.round(hours / 24);
  return `${days} дн назад`;
}

export function fromNow(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diff = date.getTime() - Date.now();
  if (diff <= 15_000) return "скоро";
  const min = Math.round(diff / 60000);
  if (min < 1) return "меньше минуты";
  if (min < 60) return `через ${min} мин`;
  const hours = Math.round(min / 60);
  if (hours < 24) return `через ${hours} ч`;
  return `через ${Math.round(hours / 24)} дн`;
}

export function moneyLabel(v: {
  salary_min: number | null;
  salary_max: number | null;
  salary_raw: string | null;
}): { text: string; known: boolean } {
  const min = v.salary_min;
  const max = v.salary_max;
  const raw = (v.salary_raw || "").trim();
  const lower = raw.toLowerCase();
  const fmt = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  if (min != null && max != null && min !== max) {
    return { text: `${fmt(min)}–${fmt(max)} ₽`, known: true };
  }
  const amount = min ?? max;
  if (amount == null) {
    if (raw && !lower.includes("не указан")) return { text: raw, known: true };
    return { text: "зп не указана", known: false };
  }
  if (lower.startsWith("от") || lower.includes(" от ")) return { text: `от ${fmt(amount)} ₽`, known: true };
  if (lower.startsWith("до") || lower.includes(" до ")) return { text: `до ${fmt(amount)} ₽`, known: true };
  return { text: `${fmt(amount)} ₽`, known: true };
}

export function notePreview(notes: string | null, limit = 90): string {
  const text = (notes || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > limit ? `${text.slice(0, limit).trim()}…` : text;
}

export function telegramHandle(alias: string | null | undefined): string {
  const cleaned = (alias || "").trim();
  if (!cleaned) return "";
  if (cleaned.startsWith("@") || cleaned.startsWith("+") || cleaned.includes("/")) return cleaned;
  return `@${cleaned}`;
}

export function telegramUrl(alias: string | null | undefined): string | null {
  const cleaned = normalizeTelegramAlias(alias);
  return cleaned ? `https://t.me/${cleaned}` : null;
}

export function displayUrl(url: string | null | undefined): string {
  return (url || "").replace(/^https?:\/\//, "");
}

export function normalizeHttpUrl(raw: string | null | undefined): string | null {
  const text = (raw || "").trim();
  if (!text) return null;
  return /^https?:\/\//i.test(text) ? text : `https://${text}`;
}

export function vacancyTelegramUrl(v: { telegram_url?: string | null; telegram_alias?: string | null }): string | null {
  return v.telegram_url || telegramUrl(v.telegram_alias);
}

export function normalizeEmail(raw: string | null | undefined): string | null {
  const text = (raw || "").trim().toLowerCase();
  return text || null;
}

export function normalizePhone(raw: string | null | undefined): string | null {
  const text = (raw || "").trim();
  return text || null;
}

export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

export function normalizeTelegramAlias(raw: string | null | undefined): string | null {
  let text = (raw || "").trim();
  if (!text) return null;
  text = text.replace(/^(?:https?:\/\/)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)\//i, "");
  text = text.replace(/^@/, "").split("?")[0].split("#")[0].trim().replace(/^\/+|\/+$/g, "");
  return text || null;
}

export function companyInitial(name: string | null): string {
  const trimmed = (name || "?").trim();
  return trimmed.slice(0, 1).toUpperCase();
}

export function normalizeInn(raw: string | null | undefined): string | null {
  const digits = (raw || "").replace(/\D/g, "");
  return digits.length === 10 || digits.length === 12 ? digits : null;
}

export function companyTitle(
  name: string | null | undefined,
  inn?: string | null,
  empty = "без компании",
): string {
  const n = (name || "").trim() || empty;
  const digits = normalizeInn(inn);
  return digits ? `${n} · ИНН ${digits}` : n;
}

export function ruCount(n: number, one: string, few: string, many: string): string {
  const n10 = n % 10;
  const n100 = n % 100;
  const word = n10 === 1 && n100 !== 11 ? one : n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20) ? few : many;
  return `${n} ${word}`;
}

const DWELL_STAGES = new Set(["to_apply", "waiting", "screening", "interview", "offer"]);

export function dwellStage(stage: string | null | undefined): boolean {
  return Boolean(stage && DWELL_STAGES.has(stage));
}

/** Quiet mark on a pipeline card. Hide 0d so a fresh move does not shout. */
export function dwellShort(days: number | null | undefined): string {
  if (days == null || days < 1) return "";
  return `${days}д`;
}

export function dwellLong(days: number | null | undefined): string {
  if (days == null) return "";
  if (days === 0) return "сегодня";
  return ruCount(days, "день", "дня", "дней");
}

export type HhPulseKind = "invited" | "discarded";

export function hasHh(v: {
  source?: string | null;
  source_url?: string | null;
  extra_sources?: { source?: string; source_url?: string }[];
}): boolean {
  if (v.source === "hh") return true;
  if ((v.source_url || "").includes("hh.ru")) return true;
  return (v.extra_sources || []).some(
    (item) => item.source === "hh" || (item.source_url || "").includes("hh.ru"),
  );
}

export function hhVacancyUrl(v: {
  source?: string | null;
  source_id?: string | null;
  source_url?: string | null;
  extra_sources?: { source?: string; source_id?: string; source_url?: string }[];
}): string | null {
  const fromUrl = (url?: string | null) => {
    const text = (url || "").split("?")[0];
    return /hh\.ru\/vacancy\/\d+/.test(text) ? text : null;
  };
  if (v.source === "hh" && v.source_id) return `https://hh.ru/vacancy/${v.source_id}`;
  const direct = fromUrl(v.source_url);
  if (direct) return direct;
  for (const item of v.extra_sources || []) {
    if (item.source === "hh" && item.source_id) return `https://hh.ru/vacancy/${item.source_id}`;
    const extra = fromUrl(item.source_url);
    if (extra) return extra;
  }
  return null;
}

export function hhPulseLabel(pulse: string | null | undefined): string {
  if (pulse === "invited") return "hh пригласил";
  if (pulse === "discarded") return "hh отказал";
  return "";
}

const WEEKDAYS = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];

export type NextStepKind = "screening" | "interview" | "offer_deadline";

export const NEXT_STEP_KINDS: { value: NextStepKind; label: string }[] = [
  { value: "screening", label: "скрин" },
  { value: "interview", label: "собес" },
  { value: "offer_deadline", label: "оффер до" },
];

export function toDatetimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const match = iso.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/);
  return match ? match[1] : "";
}

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

export function wallDate(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function addDaysYmd(ymd: string, days: number) {
  const [y, m, d] = ymd.split("-").map(Number);
  const date = new Date(y, m - 1, d + days);
  return wallDate(date);
}

export function todayYmd() {
  return wallDate(new Date());
}

/** Next occurrence of weekday: 1=пн … 7=вс. If that day is today, jump a week. */
export function nextWeekdayYmd(weekday: number) {
  const now = new Date();
  const cur = now.getDay() === 0 ? 7 : now.getDay();
  let delta = (weekday - cur + 7) % 7;
  if (delta === 0) delta = 7;
  return addDaysYmd(todayYmd(), delta);
}

export function addMinutesLocal(iso: string, minutes: number): string {
  const date = parseWallClock(iso.length === 16 ? `${iso}:00` : iso);
  if (!date) return iso;
  date.setMinutes(date.getMinutes() + minutes);
  return `${wallDate(date)}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

export function minutesSpan(startIso: string, endIso?: string | null): number {
  const start = parseWallClock(startIso.length === 16 ? `${startIso}:00` : startIso);
  const end = endIso ? parseWallClock(endIso.length === 16 ? `${endIso}:00` : endIso) : null;
  if (!start || !end) return 60;
  return Math.max(15, Math.round((end.getTime() - start.getTime()) / 60_000));
}

export function parseWallClock(iso: string): Date | null {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (match) {
    return new Date(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3]),
      Number(match[4]),
      Number(match[5]),
    );
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatNextStepBadge(at: string | null | undefined, kind?: string | null): string | null {
  if (!at) return null;
  const date = parseWallClock(at);
  if (!date) return null;
  const time = `${WEEKDAYS[date.getDay()]} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  return kind === "offer_deadline" ? `до ${time}` : time;
}
