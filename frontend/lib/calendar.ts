import {
  NEXT_STEP_KINDS,
  parseWallClock,
  vacancyTelegramUrl,
  type NextStepKind,
} from "./format";

const MEETING =
  /https?:\/\/[^\s<>"']*(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|telemost\.yandex|whereby\.com|facetime\.apple)/i;

export type CalendarEventInput = {
  id: number;
  title: string;
  company: string | null;
  notes: string | null;
  source_url: string | null;
  telegram_alias?: string | null;
  telegram_url?: string | null;
  next_step_at: string | null | undefined;
  next_step_kind: string | null | undefined;
  label?: string | null;
  ends_at?: string | null;
};

function kindLabel(kind: string | null | undefined): string {
  return NEXT_STEP_KINDS.find((k) => k.value === kind)?.label ?? "собес";
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function wallStamp(date: Date): string {
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}T${pad(date.getHours())}${pad(date.getMinutes())}00`;
}

function addMinutes(date: Date, minutes: number): Date {
  return new Date(date.getTime() + minutes * 60_000);
}

function durationMinutes(kind: string | null | undefined): number {
  return kind === "offer_deadline" || kind === "assignment" ? 30 : 60;
}

function endOf(input: CalendarEventInput, start: Date): Date {
  if (input.ends_at) {
    const parsed = parseWallClock(input.ends_at);
    if (parsed && parsed.getTime() > start.getTime()) return parsed;
  }
  return addMinutes(start, durationMinutes(input.next_step_kind));
}

function icsEscape(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
}

function foldIcs(line: string): string {
  const out: string[] = [];
  let rest = line;
  while (rest.length > 73) {
    out.push(rest.slice(0, 73));
    rest = ` ${rest.slice(73)}`;
  }
  out.push(rest);
  return out.join("\r\n");
}

export function extractMeetingUrl(text: string | null | undefined): string | null {
  const hay = text || "";
  return hay.match(MEETING)?.[0]?.replace(/[),.;]+$/, "") ?? null;
}

export function eventLocation(input: CalendarEventInput): string | null {
  const fromNotes = extractMeetingUrl(input.notes);
  if (fromNotes) return fromNotes;
  return vacancyTelegramUrl(input);
}

export function eventTitle(input: CalendarEventInput): string {
  const company = (input.company || "").trim() || "без компании";
  const role = (input.title || "").trim() || "вакансия";
  const step = (input.label || "").trim() || kindLabel(input.next_step_kind);
  return `${step} · ${company} — ${role}`;
}

export function eventDetails(input: CalendarEventInput): string {
  const lines = ["HuntOS — следующий шаг"];
  if (input.source_url) lines.push(input.source_url);
  const tg = vacancyTelegramUrl(input);
  if (tg) lines.push(tg);
  const notes = (input.notes || "").replace(/\s+/g, " ").trim();
  if (notes) lines.push(notes.slice(0, 400));
  return lines.join("\n");
}

export function googleCalendarUrl(input: CalendarEventInput): string | null {
  if (!input.next_step_at) return null;
  const start = parseWallClock(input.next_step_at);
  if (!start) return null;
  const end = endOf(input, start);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: eventTitle(input),
    dates: `${wallStamp(start)}/${wallStamp(end)}`,
    details: eventDetails(input),
  });
  const location = eventLocation(input);
  if (location) params.set("location", location);
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function vacancyIcs(input: CalendarEventInput): string | null {
  if (!input.next_step_at) return null;
  const start = parseWallClock(input.next_step_at);
  if (!start) return null;
  const end = endOf(input, start);
  const location = eventLocation(input);
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//HuntOS//Job CRM//RU",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:hunt-event-${input.id}@hunt.local`,
    `DTSTAMP:${stamp}`,
    `DTSTART:${wallStamp(start)}`,
    `DTEND:${wallStamp(end)}`,
    foldIcs(`SUMMARY:${icsEscape(eventTitle(input))}`),
    foldIcs(`DESCRIPTION:${icsEscape(eventDetails(input))}`),
  ];
  if (location) lines.push(foldIcs(`LOCATION:${icsEscape(location)}`));
  lines.push("END:VEVENT", "END:VCALENDAR");
  return `${lines.join("\r\n")}\r\n`;
}

export function downloadVacancyIcs(input: CalendarEventInput): boolean {
  const body = vacancyIcs(input);
  if (!body) return false;
  const blob = new Blob([body], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `hunt-${input.id}.ics`;
  a.click();
  URL.revokeObjectURL(url);
  return true;
}

export function downloadPingIcs(input: { id: number; title: string; ping_at: string; details?: string }): boolean {
  const start = parseWallClock(input.ping_at);
  if (!start) return false;
  const end = addMinutes(start, 45);
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const details = input.details || "HuntOS — один слот пинга на пачку.";
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//HuntOS//Job CRM//RU",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:hunt-ping-${input.id}@hunt.local`,
    `DTSTAMP:${stamp}`,
    `DTSTART:${wallStamp(start)}`,
    `DTEND:${wallStamp(end)}`,
    foldIcs(`SUMMARY:${icsEscape(input.title)}`),
    foldIcs(`DESCRIPTION:${icsEscape(details)}`),
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  const body = `${lines.join("\r\n")}\r\n`;
  const blob = new Blob([body], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `hunt-ping-${input.id}.ics`;
  a.click();
  URL.revokeObjectURL(url);
  return true;
}

export function pingEventTitle(label: string, count: number): string {
  const name = (label || "").trim() || "без тезиса";
  return `пинг волны · ${name}, ${ruCards(count)}`;
}

function ruCards(n: number): string {
  const abs = Math.abs(n);
  if (abs % 100 >= 11 && abs % 100 <= 14) return `${abs} карточек`;
  const tail = abs % 10;
  if (tail === 1) return `${abs} карточка`;
  if (tail >= 2 && tail <= 4) return `${abs} карточки`;
  return `${abs} карточек`;
}

export function isNextStepKind(value: string): value is NextStepKind {
  return NEXT_STEP_KINDS.some((k) => k.value === value);
}
