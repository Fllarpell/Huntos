from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hunt_thesis import HuntThesis
from app.models.outreach_wave import OutreachWave
from app.models.vacancy import HhPulse, PipelineStage, Vacancy

NUDGE_AFTER_DAYS = 5


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def silence_start(vacancy: Vacancy) -> datetime | None:
    return vacancy.pinged_at or vacancy.outreach_at or vacancy.last_touch_at


def silence_days(vacancy: Vacancy, now: datetime | None = None) -> int | None:
    start = silence_start(vacancy)
    if start is None:
        return None
    delta = (now or _now()) - start
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() // 86400)


def ping_due(vacancy: Vacancy, now: datetime | None = None) -> bool:
    if vacancy.pipeline_stage != PipelineStage.WAITING:
        return False
    if vacancy.hh_pulse in {HhPulse.INVITED, HhPulse.DISCARDED}:
        return False
    instant = now or _now()
    if vacancy.next_step_at and vacancy.next_step_at >= instant:
        return False
    days = silence_days(vacancy, instant)
    return days is not None and days >= NUDGE_AFTER_DAYS


def annotate_ping(vacancy: Vacancy) -> tuple[bool, int | None]:
    return ping_due(vacancy), silence_days(vacancy)


async def nudge_queue(session: AsyncSession, user_id: int) -> dict:
    now = _now()
    rows = (
        await session.execute(
            select(Vacancy).where(
                Vacancy.user_id == user_id,
                Vacancy.duplicate_of_id.is_(None),
                Vacancy.pipeline_stage == PipelineStage.WAITING,
            )
        )
    ).scalars().all()
    due = [row for row in rows if ping_due(row, now)]
    due.sort(key=lambda row: silence_days(row, now) or 0, reverse=True)

    waves = (
        await session.execute(
            select(OutreachWave)
            .where(OutreachWave.user_id == user_id)
            .order_by(OutreachWave.id.desc())
        )
    ).scalars().all()
    owner: dict[int, int] = {}
    for wave in waves:
        for vacancy_id in wave.vacancy_ids or []:
            owner.setdefault(int(vacancy_id), wave.thesis_id)

    theses = (
        await session.execute(select(HuntThesis).where(HuntThesis.user_id == user_id))
    ).scalars().all()
    names = {row.id: row.name for row in theses}

    buckets: dict[int | None, list[Vacancy]] = defaultdict(list)
    for row in due:
        buckets[owner.get(row.id)].append(row)

    groups = []
    for thesis_id, items in buckets.items():
        groups.append(
            {
                "thesis_id": thesis_id,
                "thesis_name": names.get(thesis_id) if thesis_id is not None else None,
                "items": items,
            }
        )
    groups.sort(key=lambda g: (g["thesis_id"] is None, -(len(g["items"]))))
    return {
        "after_days": NUDGE_AFTER_DAYS,
        "total": len(due),
        "groups": groups,
    }
