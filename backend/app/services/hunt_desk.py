from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import PipelineStage, Vacancy


def _today() -> date:
    return datetime.now(UTC).replace(tzinfo=None).date()


async def hunt_desk(session: AsyncSession, user_id: int, *, days: int = 14) -> dict:
    """Flow of the hunt: inbox pressure and arrivals. Not a calendar of applications."""
    window = max(7, min(30, days))
    today = _today()
    lo = datetime.combine(today - timedelta(days=window - 1), datetime.min.time())
    base = [
        Vacancy.user_id == user_id,
        Vacancy.duplicate_of_id.is_(None),
    ]
    inbox_total = (
        await session.execute(
            select(func.count(Vacancy.id)).where(*base, Vacancy.pipeline_stage == PipelineStage.INBOX)
        )
    ).scalar_one()
    waiting_total = (
        await session.execute(
            select(func.count(Vacancy.id)).where(*base, Vacancy.pipeline_stage == PipelineStage.WAITING)
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(func.date(Vacancy.created_at), func.count(Vacancy.id)).where(
                *base,
                Vacancy.pipeline_stage != PipelineStage.TRASH,
                Vacancy.created_at >= lo,
            ).group_by(func.date(Vacancy.created_at))
        )
    ).all()
    by_day = {str(day): int(count) for day, count in rows if day}
    density = []
    for offset in range(window):
        day = today - timedelta(days=window - 1 - offset)
        key = day.isoformat()
        density.append({"date": key, "new": by_day.get(key, 0)})
    return {
        "inbox_total": int(inbox_total or 0),
        "waiting_total": int(waiting_total or 0),
        "density": density,
    }
