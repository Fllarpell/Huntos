from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hunt_thesis import HuntThesis
from app.models.vacancy import PipelineStage, Vacancy
from app.services.hunts import match_filters

REPLY_STAGES = (PipelineStage.SCREENING, PipelineStage.INTERVIEW, PipelineStage.OFFER)
OUTREACH_STAGES = (
    PipelineStage.WAITING,
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


async def matching_vacancies(session: AsyncSession, thesis: HuntThesis) -> list[Vacancy]:
    rows = (
        await session.execute(select(Vacancy).where(*match_filters(thesis, window=True)).limit(400))
    ).scalars().all()
    return list(rows)


def evaluate(thesis: HuntThesis, rows: list[Vacancy]) -> dict:
    now = _now()
    age_days = max(0, (now - thesis.created_at).days) if thesis.created_at else 0
    scores = [v.match_score for v in rows if v.match_score is not None]
    median = _median(scores)
    nda = sum(1 for v in rows if (v.company or "").strip().lower() == "nda")
    fresh = sum(
        1
        for v in rows
        if v.published_at and (now - v.published_at) <= timedelta(hours=24)
    )
    outreach = sum(
        1
        for v in rows
        if v.pipeline_stage in OUTREACH_STAGES or v.outreach_at is not None
    )
    replies = sum(1 for v in rows if v.pipeline_stage in REPLY_STAGES)
    sample = len(rows)
    window = thesis.days or 14
    min_sample = thesis.min_sample or 8
    bar = thesis.min_median_match or 55

    if sample == 0:
        verdict, reason = (
            ("dead", "Выборка пустая — такого сегмента сейчас нет")
            if age_days >= min(window, 5)
            else ("weak", "Пока нет вакансий в выборке, рано хоронить тезис")
        )
    elif sample < min_sample:
        verdict, reason = (
            ("dead", f"Мало вакансий: {sample} из {min_sample} за {window} дн.")
            if age_days >= window
            else ("weak", f"Пока {sample} вакансий из {min_sample}. Окно ещё идёт.")
        )
    elif median is not None and median < bar:
        verdict, reason = "dead", f"Медианный match {median} ниже порога {bar} — сегмент не твой"
    elif outreach >= 5 and replies == 0:
        verdict, reason = "dead", f"{outreach} касаний без ответа. Канал или тезис не работают"
    elif outreach >= 2 and replies == 0:
        verdict, reason = "weak", f"{outreach} касаний, ответов нет. Ещё рано, но сигнал плохой"
    else:
        verdict, reason = "alive", "Сегмент живой: хватает выборки и match не просел"

    return {
        "verdict": verdict,
        "reason": reason,
        "sample": sample,
        "median_match": median,
        "nda_share": round(nda / sample, 2) if sample else 0,
        "fresh_24h": fresh,
        "outreach": outreach,
        "replies": replies,
        "age_days": age_days,
        "window_days": window,
    }


PACK_DEFAULT = 20
PACK_MAX = 50
PACK_LIST = 80


def rank_inbox_pack(rows: list[Vacancy]) -> list[Vacancy]:
    inbox = [row for row in rows if row.pipeline_stage == PipelineStage.INBOX]
    inbox.sort(
        key=lambda row: (
            0 if row.telegram_alias or row.contact_email or row.contact_phone else 1,
            -(row.match_score if row.match_score is not None else -1),
            -(row.published_at.timestamp() if row.published_at else 0),
        )
    )
    return inbox


async def refresh_thesis(session: AsyncSession, thesis: HuntThesis) -> dict:
    rows = await matching_vacancies(session, thesis)
    stats = evaluate(thesis, rows)
    thesis.last_verdict = stats["verdict"]
    thesis.last_reason = stats["reason"][:512]
    thesis.last_evaluated_at = _now()
    await session.commit()
    return stats
