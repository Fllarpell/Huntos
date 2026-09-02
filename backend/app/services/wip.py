from __future__ import annotations

from datetime import UTC, datetime

from app.models.vacancy import PipelineStage, Vacancy

STALE_AFTER = {
    PipelineStage.TO_APPLY: 3,
    PipelineStage.WAITING: 7,
    PipelineStage.SCREENING: 7,
    PipelineStage.INTERVIEW: 7,
    PipelineStage.OFFER: 3,
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def touch(vacancy: Vacancy) -> None:
    vacancy.last_touch_at = _now()


def enter_stage(vacancy: Vacancy, stage: PipelineStage) -> bool:
    """Move the card. Dwell clock restarts only when the column actually changes."""
    if vacancy.pipeline_stage == stage:
        return False
    vacancy.pipeline_stage = stage
    vacancy.stage_entered_at = _now()
    touch(vacancy)
    return True


def dwell_start(vacancy: Vacancy) -> datetime | None:
    return vacancy.stage_entered_at or vacancy.last_touch_at or vacancy.created_at


def dwell_days(vacancy: Vacancy, now: datetime | None = None) -> int | None:
    start = dwell_start(vacancy)
    if start is None:
        return None
    delta = (now or _now()) - start
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() // 86400)


def dwell_stale(vacancy: Vacancy, days: int | None = None) -> bool:
    lived = dwell_days(vacancy) if days is None else days
    if lived is None:
        return False
    bar = STALE_AFTER.get(vacancy.pipeline_stage)
    return bar is not None and lived >= bar


def annotate_dwell(vacancy: Vacancy) -> tuple[int | None, bool]:
    days = dwell_days(vacancy)
    return days, dwell_stale(vacancy, days)
