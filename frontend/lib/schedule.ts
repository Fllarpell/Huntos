export const HOUR_PX = 56;
export const PING_MINUTES = 45;
export const DURATIONS = [30, 45, 60, 90, 120];

export function defaultMinutes(kind: string | null | undefined, ping = false): number {
  if (ping) return PING_MINUTES;
  return kind === "offer_deadline" || kind === "assignment" ? 30 : 60;
}

export function clockMinutes(iso: string | null | undefined): number | null {
  const match = iso?.match(/[T ](\d{2}):(\d{2})/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function hmRange(startIso: string, endIso?: string | null): string {
  const startMin = clockMinutes(startIso);
  const endMin = clockMinutes(endIso || "");
  if (startMin == null) return "";
  const start = `${pad2(Math.floor(startMin / 60))}:${pad2(startMin % 60)}`;
  if (endMin == null || endMin === startMin) return start;
  return `${start}–${pad2(Math.floor(endMin / 60))}:${pad2(endMin % 60)}`;
}

export type TimedItem = {
  key: string;
  startMin: number;
  endMin: number;
};

export type LaidOut<T extends TimedItem> = T & { col: number; cols: number };

export function layoutDay<T extends TimedItem>(items: T[]): LaidOut<T>[] {
  const sorted = [...items].sort((a, b) => a.startMin - b.startMin || a.endMin - b.endMin || a.key.localeCompare(b.key));
  const groups: T[][] = [];
  let current: T[] = [];
  let currentEnd = -1;
  for (const item of sorted) {
    if (!current.length || item.startMin < currentEnd) {
      current.push(item);
      currentEnd = Math.max(currentEnd, item.endMin);
      continue;
    }
    groups.push(current);
    current = [item];
    currentEnd = item.endMin;
  }
  if (current.length) groups.push(current);

  const out: LaidOut<T>[] = [];
  for (const group of groups) {
    const colEnd: number[] = [];
    const placed: LaidOut<T>[] = [];
    for (const item of group) {
      let col = colEnd.findIndex((end) => end <= item.startMin);
      if (col < 0) {
        col = colEnd.length;
        colEnd.push(item.endMin);
      } else {
        colEnd[col] = item.endMin;
      }
      placed.push({ ...item, col, cols: 1 });
    }
    const cols = Math.max(1, colEnd.length);
    for (const item of placed) out.push({ ...item, cols });
  }
  return out;
}

export function hourWindow(items: { startMin: number; endMin: number }[], nowMin?: number | null): { startHour: number; endHour: number } {
  let lo = 7 * 60;
  let hi = 22 * 60;
  for (const item of items) {
    lo = Math.min(lo, item.startMin);
    hi = Math.max(hi, item.endMin);
  }
  if (nowMin != null) {
    lo = Math.min(lo, nowMin);
    hi = Math.max(hi, nowMin + 30);
  }
  const startHour = Math.max(0, Math.min(7, Math.floor(lo / 60)));
  const endHour = Math.min(24, Math.max(22, Math.ceil(hi / 60)));
  return { startHour, endHour: Math.max(startHour + 1, endHour) };
}
