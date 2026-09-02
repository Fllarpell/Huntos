from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.vacancy import NextStepKind, PipelineStage, Vacancy
from app.models.vacancy_event import VacancyEvent
from app.services.vacancy_events import display_labels, event_end, kind_label

LIVE_STAGES = {
    PipelineStage.INBOX,
    PipelineStage.TO_APPLY,
    PipelineStage.WAITING,
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
}

KIND_RANK = {
    NextStepKind.OFFER_DEADLINE: 3,
    NextStepKind.INTERVIEW: 2,
    NextStepKind.SCREENING: 1,
}

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def _today() -> date:
    return datetime.now(ZoneInfo(settings.google_calendar_timezone)).date()


def _kind(event: VacancyEvent) -> NextStepKind:
    return event.kind or NextStepKind.INTERVIEW


def _company(vacancy: Vacancy) -> str:
    return (vacancy.company or "").strip() or "без компании"


def _time(instant: datetime) -> str:
    return f"{instant.hour:02d}:{instant.minute:02d}"


def _day_label(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def _pressure(row: tuple[Vacancy, VacancyEvent, str]) -> tuple:
    vacancy, event, _label = row
    return (
        KIND_RANK.get(_kind(event), 0),
        vacancy.match_score or 0,
        vacancy.salary_max or vacancy.salary_min or 0,
        -(event.starts_at.hour * 60 + event.starts_at.minute),
    )


def _item(vacancy: Vacancy, event: VacancyEvent, label: str) -> dict:
    return {
        "id": vacancy.id,
        "event_id": event.id,
        "company": vacancy.company,
        "title": vacancy.title,
        "label": label,
        "next_step_at": event.starts_at,
        "ends_at": event_end(event),
        "next_step_kind": _kind(event),
        "match_score": vacancy.match_score,
        "pipeline_stage": vacancy.pipeline_stage,
    }


def _step_line(vacancy: Vacancy, event: VacancyEvent, label: str) -> str:
    end = event_end(event)
    return f"{_company(vacancy)} — {label} {_time(event.starts_at)}–{_time(end)}"


def collision_hint(rows: list[tuple[Vacancy, VacancyEvent, str]]) -> str:
    ordered = sorted(rows, key=_pressure, reverse=True)
    lines = [_step_line(*row) for row in ordered]
    if len(lines) == 2:
        return f"В этот день два шага: {lines[0]} и {lines[1]}."
    return f"В этот день {len(lines)} шага: " + "; ".join(lines) + "."


def group_days(rows: list[tuple[Vacancy, VacancyEvent, str]]) -> list[dict]:
    buckets: dict[date, list[tuple[Vacancy, VacancyEvent, str]]] = defaultdict(list)
    for row in rows:
        buckets[row[1].starts_at.date()].append(row)
    days: list[dict] = []
    for day in sorted(buckets):
        items = buckets[day]
        if len(items) < 2:
            continue
        ordered = sorted(items, key=_pressure, reverse=True)
        days.append(
            {
                "date": day.isoformat(),
                "label": _day_label(day),
                "hint": collision_hint(ordered),
                "press_id": ordered[0][0].id,
                "items": [_item(*row) for row in ordered],
            }
        )
    return days


def collision_index(days: list[dict]) -> dict[int, dict]:
    index: dict[int, dict] = {}
    for day in days:
        peers = len(day["items"])
        for item in day["items"]:
            index[item["id"]] = {
                "hint": day["hint"],
                "peers": peers,
                "press_id": day["press_id"],
                "date": day["date"],
            }
    return index


async def _load_rows(
    session: AsyncSession,
    user_id: int,
    *,
    lo: datetime | None = None,
    hi: datetime | None = None,
    from_today: bool = False,
) -> list[tuple[Vacancy, VacancyEvent, str]]:
    stmt = (
        select(VacancyEvent, Vacancy)
        .join(Vacancy, VacancyEvent.vacancy_id == Vacancy.id)
        .where(
            Vacancy.user_id == user_id,
            Vacancy.duplicate_of_id.is_(None),
            Vacancy.pipeline_stage.in_(LIVE_STAGES),
        )
    )
    if lo is not None:
        stmt = stmt.where(VacancyEvent.starts_at >= lo)
    if hi is not None:
        stmt = stmt.where(VacancyEvent.starts_at <= hi)
    pairs = (await session.execute(stmt)).all()
    if from_today:
        today = _today()
        pairs = [row for row in pairs if row[0].starts_at.date() >= today]
    by_vacancy: dict[int, list[VacancyEvent]] = defaultdict(list)
    vacancies: dict[int, Vacancy] = {}
    for event, vacancy in pairs:
        by_vacancy[vacancy.id].append(event)
        vacancies[vacancy.id] = vacancy
    labels: dict[int, str] = {}
    for events in by_vacancy.values():
        events.sort(key=lambda row: row.starts_at)
        labels.update(display_labels(events))
    rows = [
        (vacancies[event.vacancy_id], event, labels.get(event.id) or kind_label(event.kind))
        for event, _vacancy in pairs
    ]
    rows.sort(key=lambda row: row[1].starts_at)
    return rows


async def ranged_meetings(session: AsyncSession, user_id: int, *, past_days: int = 40, future_days: int = 70) -> list[dict]:
    today = _today()
    lo = datetime.combine(today - timedelta(days=past_days), datetime.min.time())
    hi = datetime.combine(today + timedelta(days=future_days), datetime.max.time())
    return [_item(*row) for row in await _load_rows(session, user_id, lo=lo, hi=hi)]


async def collision_snapshot(session: AsyncSession, user_id: int) -> tuple[list[dict], list[dict], dict[int, dict]]:
    rows = await _load_rows(session, user_id, from_today=True)
    days = group_days(rows)
    return days, [_item(*row) for row in rows], collision_index(days)
