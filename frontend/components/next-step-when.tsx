"use client";

import { NEXT_STEP_KINDS, addDaysYmd, nextWeekdayYmd, todayYmd } from "@/lib/format";

const DEFAULT_TIME = "15:00";

const TIMES = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"];

function split(value: string) {
  const match = value.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return match ? { date: match[1], time: match[2] } : { date: "", time: "" };
}

function chip(on: boolean) {
  return `rounded-full px-2.5 py-1 text-[12px] transition ${
    on ? "bg-accent/18 text-accent ring-1 ring-accent/35" : "bg-white/5 text-muted hover:bg-white/8 hover:text-white"
  }`;
}

export function NextStepWhen({
  value,
  kind,
  onChange,
  showKind = true,
}: {
  value: string;
  kind: string;
  onChange: (next: { next_step_at: string; next_step_kind: string }) => void;
  showKind?: boolean;
}) {
  const { date, time } = split(value);
  const today = todayYmd();

  function setWhen(nextDate: string, nextTime: string, nextKind = kind) {
    if (!nextDate) {
      onChange({ next_step_at: "", next_step_kind: "" });
      return;
    }
    const clock = nextTime || time || DEFAULT_TIME;
    onChange({
      next_step_at: `${nextDate}T${clock}`,
      next_step_kind: nextKind || "interview",
    });
  }

  const dayChips = [
    { label: "сегодня", ymd: today },
    { label: "завтра", ymd: addDaysYmd(today, 1) },
    { label: "пн", ymd: nextWeekdayYmd(1) },
    { label: "вт", ymd: nextWeekdayYmd(2) },
    { label: "ср", ymd: nextWeekdayYmd(3) },
    { label: "чт", ymd: nextWeekdayYmd(4) },
    { label: "пт", ymd: nextWeekdayYmd(5) },
  ];

  return (
    <div className="space-y-3">
      {showKind && (
        <div className="flex flex-wrap gap-1.5">
          {NEXT_STEP_KINDS.map((o) => (
            <button
              key={o.value}
              type="button"
              className={chip(kind === o.value)}
              onClick={() => {
                if (!date) onChange({ next_step_at: "", next_step_kind: o.value });
                else setWhen(date, time || DEFAULT_TIME, o.value);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {dayChips.map((o) => (
          <button
            key={o.label}
            type="button"
            className={chip(date === o.ymd)}
            onClick={() => setWhen(o.ymd, time || DEFAULT_TIME)}
          >
            {o.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input type="date" value={date} onChange={(e) => setWhen(e.target.value, time || DEFAULT_TIME)} />
        <select value={time || DEFAULT_TIME} onChange={(e) => setWhen(date || today, e.target.value)}>
          {!TIMES.includes(time) && time && <option value={time}>{time}</option>}
          {TIMES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {TIMES.map((t) => (
          <button key={t} type="button" className={chip(time === t)} onClick={() => setWhen(date || today, t)}>
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
