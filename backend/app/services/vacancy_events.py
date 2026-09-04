from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import NextStepKind, PipelineStage, Vacancy
from app.models.vacancy_event import VacancyEvent
from app.services.wip import enter_stage

KIND_LABEL = {
    NextStepKind.SCREENING: "скрининг",
    NextStepKind.INTERVIEW: "собес",
    NextStepKind.ASSIGNMENT: "тех задание",
    NextStepKind.OFFER_DEADLINE: "оффер до",
}

STEP_STAGE = {
    NextStepKind.SCREENING: PipelineStage.SCREENING,
    NextStepKind.INTERVIEW: PipelineStage.INTERVIEW,
}

STAGE_RANK = {
    PipelineStage.INBOX: 0,
    PipelineStage.TO_APPLY: 1,
    PipelineStage.WAITING: 2,
    PipelineStage.SCREENING: 3,
    PipelineStage.INTERVIEW: 4,
    PipelineStage.OFFER: 5,
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def kind_label(kind: object) -> str:
    value = kind if isinstance(kind, NextStepKind) else NextStepKind(str(kind or "interview"))
    return KIND_LABEL.get(value, "собес")


def duration_minutes(kind: object) -> int:
    value = getattr(kind, "value", kind)
    return 30 if value in {"offer_deadline", "assignment"} else 60


def event_end(event: VacancyEvent) -> datetime:
    start = event.starts_at
    ends = event.ends_at
    if ends is not None and ends > start:
        return ends
    return start + timedelta(minutes=duration_minutes(event.kind))


def parse_kind(raw: object, fallback: NextStepKind = NextStepKind.INTERVIEW) -> NextStepKind:
    if isinstance(raw, NextStepKind):
        return raw
    try:
        return NextStepKind(str(raw)) if raw else fallback
    except ValueError:
        return fallback


async def list_events(session: AsyncSession, vacancy_id: int) -> list[VacancyEvent]:
    rows = (
        await session.execute(
            select(VacancyEvent).where(VacancyEvent.vacancy_id == vacancy_id).order_by(VacancyEvent.starts_at.asc())
        )
    ).scalars().all()
    return list(rows)


async def events_for_vacancies(session: AsyncSession, vacancy_ids: list[int]) -> dict[int, list[VacancyEvent]]:
    if not vacancy_ids:
        return {}
    rows = (
        await session.execute(
            select(VacancyEvent)
            .where(VacancyEvent.vacancy_id.in_(vacancy_ids))
            .order_by(VacancyEvent.starts_at.asc())
        )
    ).scalars().all()
    grouped: dict[int, list[VacancyEvent]] = {vid: [] for vid in vacancy_ids}
    for row in rows:
        grouped.setdefault(row.vacancy_id, []).append(row)
    return grouped


def display_labels(events: list[VacancyEvent]) -> dict[int, str]:
    interviews = [row for row in events if row.kind == NextStepKind.INTERVIEW]
    numbered = len(interviews) > 1
    out: dict[int, str] = {}
    index = 0
    for row in events:
        custom = (row.label or "").strip()
        if custom:
            out[row.id] = custom
            continue
        if row.kind == NextStepKind.INTERVIEW and numbered:
            index += 1
            out[row.id] = f"собес {index}"
            continue
        out[row.id] = kind_label(row.kind)
    return out


def refresh_next_step(vacancy: Vacancy, events: list[VacancyEvent]) -> None:
    now = _now()
    dated = [row for row in events if row.starts_at]
    future = [row for row in dated if row.starts_at >= now]
    pick = min(future, key=lambda row: row.starts_at) if future else None
    vacancy.next_step_at = pick.starts_at if pick else None
    vacancy.next_step_kind = pick.kind if pick else None
    vacancy.google_event_id = pick.google_event_id if pick else None
    vacancy.google_sync_error = pick.google_sync_error if pick else None


def promote_for_step(vacancy: Vacancy, kind: NextStepKind | None) -> bool:
    """Scoring/interview steps pull the card forward. Never demote offer/refusal."""
    target = STEP_STAGE.get(kind) if kind is not None else None
    if target is None:
        return False
    current = vacancy.pipeline_stage
    here = STAGE_RANK.get(current)
    want = STAGE_RANK.get(target)
    if here is None or want is None or here >= want:
        return False
    return enter_stage(vacancy, target)


def event_out(event: VacancyEvent, labels: dict[int, str], connected: bool) -> dict:
    return {
        "id": event.id,
        "vacancy_id": event.vacancy_id,
        "kind": event.kind,
        "starts_at": event.starts_at,
        "ends_at": event_end(event),
        "label": event.label,
        "display_label": labels.get(event.id) or kind_label(event.kind),
        "google_event_id": event.google_event_id,
        "google_sync_error": event.google_sync_error,
        "calendar_connected": connected,
    }


def events_payload(events: list[VacancyEvent], connected: bool) -> list[dict]:
    labels = display_labels(events)
    return [event_out(row, labels, connected) for row in events]


async def create_event(
    session: AsyncSession,
    vacancy: Vacancy,
    *,
    kind: NextStepKind,
    starts_at: datetime,
    label: str | None = None,
    ends_at: datetime | None = None,
) -> VacancyEvent:
    if vacancy.user_id is None:
        raise RuntimeError("vacancy without user")
    step = kind or NextStepKind.INTERVIEW
    end = ends_at if ends_at and ends_at > starts_at else starts_at + timedelta(minutes=duration_minutes(step))
    event = VacancyEvent(
        user_id=vacancy.user_id,
        vacancy_id=vacancy.id,
        kind=step,
        starts_at=starts_at,
        ends_at=end,
        label=(label or "").strip() or None,
    )
    session.add(event)
    await session.flush()
    events = await list_events(session, vacancy.id)
    refresh_next_step(vacancy, events)
    promote_for_step(vacancy, step)
    return event


async def update_event(
    session: AsyncSession,
    vacancy: Vacancy,
    event: VacancyEvent,
    *,
    kind: NextStepKind | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    label: str | None | object = ...,
) -> VacancyEvent:
    span = event_end(event) - event.starts_at
    old_kind = event.kind
    if kind is not None and kind != event.kind:
        defaulted = event_end(event) == event.starts_at + timedelta(minutes=duration_minutes(old_kind))
        event.kind = kind
        if ends_at is None and defaulted:
            event.ends_at = event.starts_at + timedelta(minutes=duration_minutes(kind))
            span = event.ends_at - event.starts_at
    if starts_at is not None and starts_at != event.starts_at:
        event.starts_at = starts_at
        if ends_at is None:
            event.ends_at = starts_at + span
    if ends_at is not None:
        event.ends_at = ends_at if ends_at > event.starts_at else event.starts_at + timedelta(minutes=15)
    elif event.ends_at is None:
        event.ends_at = event.starts_at + span
    if label is not ...:
        event.label = (label or "").strip() or None
    await session.flush()
    events = await list_events(session, vacancy.id)
    refresh_next_step(vacancy, events)
    promote_for_step(vacancy, event.kind)
    return event


def pick_next_event(events: list[VacancyEvent]) -> VacancyEvent | None:
    if not events:
        return None
    now = _now()
    future = [row for row in events if row.starts_at >= now]
    if future:
        return min(future, key=lambda row: row.starts_at)
    return events[0]


async def mirror_next_step(session: AsyncSession, vacancy: Vacancy) -> None:
    """Keep a single event in sync when the old vacancy.next_step_* fields are patched."""
    events = await list_events(session, vacancy.id)
    if vacancy.next_step_at is None:
        if len(events) == 1:
            await session.delete(events[0])
            await session.flush()
            refresh_next_step(vacancy, [])
        else:
            refresh_next_step(vacancy, events)
        return
    kind = vacancy.next_step_kind or NextStepKind.INTERVIEW
    if not events:
        if vacancy.user_id is None:
            return
        event = VacancyEvent(
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            kind=kind,
            starts_at=vacancy.next_step_at,
            ends_at=vacancy.next_step_at + timedelta(minutes=duration_minutes(kind)),
            google_event_id=vacancy.google_event_id,
            google_sync_error=vacancy.google_sync_error,
        )
        session.add(event)
        await session.flush()
        refresh_next_step(vacancy, [event])
        return
    target = pick_next_event(events)
    if target is None:
        return
    span = event_end(target) - target.starts_at
    target.starts_at = vacancy.next_step_at
    target.kind = kind
    target.ends_at = target.starts_at + span
    await session.flush()
    refresh_next_step(vacancy, await list_events(session, vacancy.id))
