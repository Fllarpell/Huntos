"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { HOUR_PX, hourWindow, layoutDay } from "@/lib/schedule";

export type GridBlock = {
  key: string;
  ymd: string;
  startMin: number;
  endMin: number;
  range: string;
  title: string;
  sub: string;
  kind: "screening" | "interview" | "assignment" | "offer_deadline" | "ping";
  collision: boolean;
  vacancyId: number | null;
  eventId: number | null;
};

function blockClass(block: GridBlock) {
  if (block.kind === "ping" || block.collision) {
    return "border-amber-400/30 bg-amber-400/18 text-amber-50";
  }
  if (block.kind === "offer_deadline" || block.kind === "assignment") {
    return "border-accent/35 bg-accent/18 text-accent";
  }
  return "border-sky-400/25 bg-sky-400/16 text-ink";
}

function nowMinutes(date: Date) {
  return date.getHours() * 60 + date.getMinutes();
}

export function TimedGrid({
  days,
  items,
  today,
  onOpen,
  onDelete,
}: {
  days: string[];
  items: GridBlock[];
  today: string;
  onOpen: (vacancyId: number) => void;
  onDelete: (eventId: number) => void;
}) {
  const [now, setNow] = useState(() => new Date());
  const scroller = useRef<HTMLDivElement>(null);
  const { startHour, endHour } = useMemo(() => {
    const nowMin = days.includes(today) ? nowMinutes(new Date()) : null;
    return hourWindow(items, nowMin);
  }, [days, items, today]);
  const hours = Array.from({ length: endHour - startHour }, (_, i) => startHour + i);
  const height = hours.length * HOUR_PX;

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    const focus = days.includes(today) ? nowMinutes(new Date()) : 10 * 60;
    const top = ((focus - startHour * 60) / 60) * HOUR_PX - HOUR_PX * 1.5;
    node.scrollTop = Math.max(0, top);
  }, [startHour, days, today]);

  const byDay = useMemo(() => {
    const map = new Map<string, GridBlock[]>();
    for (const day of days) map.set(day, []);
    for (const item of items) {
      map.get(item.ymd)?.push(item);
    }
    return map;
  }, [days, items]);

  return (
    <div ref={scroller} className="min-h-0 flex-1 overflow-auto rounded-2xl border border-line">
      <div className="sticky top-0 z-20 grid border-b border-line bg-bg-soft" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(0, 1fr))` }}>
        <div className="border-r border-line" />
        {days.map((ymd) => {
          const date = new Date(Number(ymd.slice(0, 4)), Number(ymd.slice(5, 7)) - 1, Number(ymd.slice(8, 10)));
          const isToday = ymd === today;
          return (
            <div key={ymd} className={`border-r border-line px-2 py-2 text-center ${isToday ? "bg-accent/8" : ""}`}>
              <p className="text-[11px] tracking-[0.12em] text-muted uppercase">
                {["вс", "пн", "вт", "ср", "чт", "пт", "сб"][date.getDay()]}
              </p>
              <p className={`text-[15px] tabular-nums ${isToday ? "font-semibold text-accent" : ""}`}>{date.getDate()}</p>
            </div>
          );
        })}
      </div>
      <div className="grid" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(0, 1fr))` }}>
        <div className="relative border-r border-line" style={{ height }}>
          {hours.map((hour, i) => (
            <div key={hour} className="absolute right-1 text-[11px] tabular-nums text-muted" style={{ top: i * HOUR_PX + 2 }}>
              {String(hour).padStart(2, "0")}:00
            </div>
          ))}
        </div>
        {days.map((ymd) => {
          const laid = layoutDay(byDay.get(ymd) || []);
          const isToday = ymd === today;
          const nowTop = isToday ? ((nowMinutes(now) - startHour * 60) / 60) * HOUR_PX : null;
          return (
            <div key={ymd} className={`relative border-r border-line ${isToday ? "bg-accent/4" : ""}`} style={{ height }}>
              {hours.map((hour, i) => (
                <div key={hour} className="absolute inset-x-0 border-t border-line/70" style={{ top: i * HOUR_PX }} />
              ))}
              {nowTop != null && nowTop >= 0 && nowTop <= height && (
                <div className="pointer-events-none absolute inset-x-0 z-10" style={{ top: nowTop }}>
                  <div className="absolute -left-1 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-rose-400" />
                  <div className="h-px bg-rose-400" />
                </div>
              )}
              {laid.map((block) => {
                const top = ((block.startMin - startHour * 60) / 60) * HOUR_PX;
                const h = Math.max(22, ((block.endMin - block.startMin) / 60) * HOUR_PX);
                const width = `calc(${100 / block.cols}% - 4px)`;
                const left = `calc(${(block.col / block.cols) * 100}% + 2px)`;
                return (
                  <div
                    key={block.key}
                    className={`absolute z-[1] overflow-hidden rounded-md border ${blockClass(block)}`}
                    style={{ top: top + 1, height: h - 2, left, width }}
                  >
                    <button
                      type="button"
                      disabled={!block.vacancyId}
                      onClick={() => block.vacancyId && onOpen(block.vacancyId)}
                      className="block h-full w-full px-1.5 py-1 pr-5 text-left disabled:opacity-60"
                    >
                      <span className="block truncate text-[11px] font-medium tabular-nums">{block.range}</span>
                      <span className="block truncate text-[12px] leading-4">{block.title}</span>
                      {h > 44 && <span className="mt-0.5 block truncate text-[11px] opacity-70">{block.sub}</span>}
                    </button>
                    {block.eventId != null && (
                      <button
                        type="button"
                        aria-label="Удалить шаг"
                        className="absolute right-0 top-0 rounded p-1 text-muted hover:bg-black/20 hover:text-white"
                        onClick={() => onDelete(block.eventId as number)}
                      >
                        <X size={11} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
