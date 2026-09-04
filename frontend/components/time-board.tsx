"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { api } from "@/lib/api";
import { GuideHint, GuideSpot } from "./guide";
import { addDaysYmd, NEXT_STEP_KINDS, todayYmd, wallDate } from "@/lib/format";
import type { CalendarBoard } from "@/lib/types";
import { VacancyDrawer } from "./vacancy-drawer";
import { TimedGrid, type GridBlock } from "./timed-grid";
import { clockMinutes, defaultMinutes, hmRange, pad2, PING_MINUTES } from "@/lib/schedule";

const DOW = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];
const MONTHS = [
  "январь",
  "февраль",
  "март",
  "апрель",
  "май",
  "июнь",
  "июль",
  "август",
  "сентябрь",
  "октябрь",
  "ноябрь",
  "декабрь",
];

function parseYmd(ymd: string) {
  const [y, m, d] = ymd.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function startOfWeek(ymd: string) {
  const date = parseYmd(ymd);
  const wd = date.getDay() === 0 ? 7 : date.getDay();
  date.setDate(date.getDate() - (wd - 1));
  return wallDate(date);
}

function startOfMonth(ymd: string) {
  const date = parseYmd(ymd);
  date.setDate(1);
  return wallDate(date);
}

function monthTitle(ymd: string) {
  const date = parseYmd(ymd);
  return `${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

function dayTitle(ymd: string) {
  const date = parseYmd(ymd);
  const dow = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"][date.getDay()];
  return `${dow}, ${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

function weekTitle(start: string) {
  const end = addDaysYmd(start, 6);
  const a = parseYmd(start);
  const b = parseYmd(end);
  if (a.getMonth() === b.getMonth()) {
    return `${a.getDate()}–${b.getDate()} ${MONTHS[a.getMonth()]}`;
  }
  return `${a.getDate()} ${MONTHS[a.getMonth()].slice(0, 3)} – ${b.getDate()} ${MONTHS[b.getMonth()].slice(0, 3)}`;
}

function ymdOf(iso: string | null | undefined) {
  return iso?.slice(0, 10) || "";
}

function endIso(startIso: string, minutes: number) {
  const start = clockMinutes(startIso) ?? 0;
  const end = start + minutes;
  return `${startIso.slice(0, 10)}T${pad2(Math.min(23, Math.floor(end / 60)))}:${pad2(end % 60)}:00`;
}

function kindLabel(kind: string | null | undefined) {
  return NEXT_STEP_KINDS.find((k) => k.value === kind)?.label ?? "собес";
}

type Chip = GridBlock;

function chipClass(chip: Chip) {
  if (chip.kind === "ping" || chip.collision) {
    return "border-amber-400/25 bg-amber-400/12 text-amber-50";
  }
  if (chip.kind === "offer_deadline" || chip.kind === "assignment") {
    return "border-accent/25 bg-accent/12 text-accent";
  }
  return "border-line bg-white/6 text-ink hover:bg-white/8";
}

export function TimeBoard() {
  const today = todayYmd();
  const router = useRouter();
  const params = useSearchParams();
  const [range, setRange] = useState<"day" | "week" | "month">("week");
  const [cursor, setCursor] = useState(today);
  const [board, setBoard] = useState<CalendarBoard | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const cal = await api.calendar();
    setBoard(cal);
  }

  useEffect(() => {
    if (params.get("tab") === "hunt") router.replace("/thesis");
  }, [params, router]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Не загрузилось"));
  }, []);

  const collisionDays = useMemo(() => new Set((board?.collisions || []).map((d) => d.date)), [board]);

  const chips = useMemo(() => {
    const items: Chip[] = [];
    for (const row of board?.meetings || []) {
      const ymd = ymdOf(row.next_step_at);
      if (!ymd) continue;
      const start = clockMinutes(row.next_step_at) ?? 15 * 60;
      const end =
        clockMinutes(row.ends_at) ?? start + defaultMinutes(row.next_step_kind);
      items.push({
        key: `m-${row.event_id ?? row.id}`,
        ymd,
        startMin: start,
        endMin: Math.max(start + 15, end),
        range: hmRange(row.next_step_at, row.ends_at || endIso(row.next_step_at, defaultMinutes(row.next_step_kind))),
        title: `${row.label || kindLabel(row.next_step_kind)} · ${row.company || "без компании"}`,
        sub: row.title,
        kind: row.next_step_kind || "interview",
        collision: collisionDays.has(ymd),
        vacancyId: row.id,
        eventId: row.event_id ?? null,
      });
    }
    for (const slot of board?.ping_slots || []) {
      const ymd = ymdOf(slot.ping_at);
      if (!ymd) continue;
      const start = clockMinutes(slot.ping_at) ?? 11 * 60;
      items.push({
        key: `p-${slot.id}`,
        ymd,
        startMin: start,
        endMin: start + PING_MINUTES,
        range: hmRange(slot.ping_at || "", endIso(slot.ping_at || "", PING_MINUTES)),
        title: `пинг волны · ${slot.label}`,
        sub: `${slot.card_count} карточек`,
        kind: "ping",
        collision: false,
        vacancyId: (slot.vacancy_ids || [])[0] ?? null,
        eventId: null,
      });
    }
    items.sort((a, b) => a.startMin - b.startMin || a.title.localeCompare(b.title));
    return items;
  }, [board, collisionDays]);

  const days = useMemo(() => {
    if (range === "day") return [cursor];
    if (range === "week") {
      const start = startOfWeek(cursor);
      return Array.from({ length: 7 }, (_, i) => addDaysYmd(start, i));
    }
    const monthStart = startOfMonth(cursor);
    const gridStart = startOfWeek(monthStart);
    return Array.from({ length: 42 }, (_, i) => addDaysYmd(gridStart, i));
  }, [range, cursor]);

  const byDay = useMemo(() => {
    const map = new Map<string, Chip[]>();
    for (const day of days) map.set(day, []);
    for (const chip of chips) {
      const list = map.get(chip.ymd);
      if (list) list.push(chip);
    }
    return map;
  }, [chips, days]);

  function shift(delta: number) {
    if (range === "day") setCursor(addDaysYmd(cursor, delta));
    else if (range === "week") setCursor(addDaysYmd(startOfWeek(cursor), delta * 7));
    else {
      const date = parseYmd(startOfMonth(cursor));
      date.setMonth(date.getMonth() + delta);
      setCursor(wallDate(date));
    }
  }

  const heading =
    range === "day"
      ? dayTitle(cursor)
      : range === "week"
        ? weekTitle(startOfWeek(cursor))
        : monthTitle(cursor);
  const inMonth = startOfMonth(cursor).slice(0, 7);

  return (
    <div className="flex h-screen min-h-0 flex-col overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center gap-x-6 gap-y-3 px-7 pt-6 pb-3">
        <GuideSpot id="time.header" className="min-w-0">
          <div className="flex items-center gap-1.5">
            <h1 className="text-[22px] font-semibold tracking-tight">Время</h1>
            <GuideHint id="time.header" />
          </div>
          <p className="mt-0.5 text-[12px] capitalize text-muted">{heading}</p>
        </GuideSpot>
        <GuideSpot id="time.range">
          <div className="flex items-center gap-5 text-[13px]">
            {(
              [
                ["day", "день"],
                ["week", "неделя"],
                ["month", "месяц"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`border-b pb-0.5 ${
                  range === id ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
                }`}
                onClick={() => setRange(id)}
              >
                {label}
              </button>
            ))}
            <GuideHint id="time.range" />
          </div>
        </GuideSpot>
        <div className="ml-auto flex items-center gap-1">
          <GuideHint id="time.grid" />
          <button type="button" className="rounded-full p-1.5 text-muted hover:bg-white/6 hover:text-white" onClick={() => shift(-1)}>
            <ChevronLeft size={16} />
          </button>
          <button type="button" className="rounded-full p-1.5 text-muted hover:bg-white/6 hover:text-white" onClick={() => shift(1)}>
            <ChevronRight size={16} />
          </button>
          <button
            type="button"
            className="ml-1 rounded-full px-3 py-1.5 text-[13px] text-muted hover:text-white"
            onClick={() => setCursor(today)}
          >
            сегодня
          </button>
        </div>
      </header>

      {error && <p className="px-7 pb-3 text-sm text-rose-200">{error}</p>}

      <GuideSpot id="time.grid" className="flex min-h-0 flex-1 flex-col px-7 pb-6">
          {!chips.length && (
            <p className="mb-3 text-[13px] text-muted">
              Пока нет скринингов, собесов и дедлайнов. Открой карточку и добавь шаг — появится здесь.
            </p>
          )}

          {range === "month" ? (
          <div className="min-h-0 flex-1 overflow-auto rounded-2xl border border-line grid grid-cols-7">
            {DOW.map((d) => (
              <div key={d} className="border-b border-line px-3 py-2 text-[11px] tracking-[0.12em] text-muted uppercase">
                {d}
              </div>
            ))}
            {days.map((ymd) => {
              const items = byDay.get(ymd) || [];
              const isToday = ymd === today;
              const muted = ymd.slice(0, 7) !== inMonth;
              const hot = collisionDays.has(ymd);
              return (
                <div
                  key={ymd}
                  className={`min-h-[110px] border-b border-r border-line px-2 py-2 ${
                    hot ? "bg-amber-400/6" : ""
                  } ${muted ? "opacity-40" : ""}`}
                >
                  <p className={`mb-2 text-[12px] tabular-nums ${isToday ? "text-accent" : "text-muted"}`}>
                    {parseYmd(ymd).getDate()}
                    {isToday ? " · сегодня" : ""}
                  </p>
                  <div className="space-y-1">
                    {items.map((chip) => (
                      <div key={chip.key} className={`relative rounded-lg border ${chipClass(chip)}`}>
                        <button
                          type="button"
                          disabled={!chip.vacancyId}
                          onClick={() => chip.vacancyId && setOpenId(chip.vacancyId)}
                          className="block w-full px-2 py-1.5 pr-6 text-left disabled:opacity-60"
                        >
                          <span className="block truncate text-[12px] font-medium">
                            {chip.range} {chip.title}
                          </span>
                          <span className="block truncate text-[11px] opacity-70">{chip.sub}</span>
                        </button>
                        {chip.eventId != null && (
                          <button
                            type="button"
                            aria-label="Удалить шаг"
                            className="absolute right-0.5 top-0.5 rounded p-1 text-muted hover:bg-white/10 hover:text-white"
                            onClick={() => {
                              void api
                                .deleteEvent(chip.eventId as number)
                                .then(() => load())
                                .catch((e) => setError(e instanceof Error ? e.message : "Не удалилось"));
                            }}
                          >
                            <X size={12} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          ) : (
            <TimedGrid
              days={days}
              items={chips.filter((chip) => days.includes(chip.ymd))}
              today={today}
              onOpen={setOpenId}
              onDelete={(eventId) => {
                void api
                  .deleteEvent(eventId)
                  .then(() => load())
                  .catch((e) => setError(e instanceof Error ? e.message : "Не удалилось"));
              }}
            />
          )}
      </GuideSpot>

      {openId != null && (
        <VacancyDrawer
          vacancyId={openId}
          onClose={() => {
            setOpenId(null);
            void load();
          }}
          onChanged={() => undefined}
        />
      )}
    </div>
  );
}
