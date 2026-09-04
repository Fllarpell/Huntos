from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hunt_thesis import HuntThesis
from app.models.vacancy import PipelineStage, Vacancy
from app.services.hunts import membership_clause
from app.services.salary_stats import corridor_from_vacancies, median as _median

REPLY_STAGES = (PipelineStage.SCREENING, PipelineStage.INTERVIEW, PipelineStage.OFFER)
OUTREACH_STAGES = (
    PipelineStage.WAITING,
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
)

PACK_DEFAULT = 20
PACK_MAX = 50
PACK_LIST = 80


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _arrived_at(row: Vacancy) -> datetime | None:
    return row.created_at or row.published_at


def _window_since(thesis: HuntThesis) -> datetime:
    return _now() - timedelta(days=max(3, thesis.days or 14))


async def matching_vacancies(session: AsyncSession, thesis: HuntThesis) -> list[Vacancy]:
    """Hunt membership in the thesis window: inbox and funnel, not only published_at."""
    since = _window_since(thesis)
    in_window = or_(Vacancy.created_at >= since, Vacancy.published_at >= since)
    rows = (
        await session.execute(select(Vacancy).where(membership_clause(thesis), in_window).limit(400))
    ).scalars().all()
    return list(rows)


def evaluate(thesis: HuntThesis, rows: list[Vacancy]) -> dict:
    now = _now()
    age_days = max(0, (now - thesis.created_at).days) if thesis.created_at else 0
    scores = [v.match_score for v in rows if v.match_score is not None]
    median = _median(scores)
    nda = sum(1 for v in rows if (v.company or "").strip().lower() == "nda")
    inbox_n = sum(1 for v in rows if v.pipeline_stage == PipelineStage.INBOX)
    fresh = sum(
        1
        for v in rows
        if (stamp := _arrived_at(v)) is not None and (now - stamp) <= timedelta(hours=24)
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
    inbox_alive = inbox_n >= max(3, min_sample // 2) or (inbox_n > 0 and fresh > 0)

    if sample == 0:
        verdict, reason = (
            ("dead", "Выборка пустая — в inbox и воронке нет вакансий сегмента")
            if age_days >= min(window, 5)
            else ("weak", "Пока нет вакансий в inbox, рано хоронить тезис")
        )
    elif sample < min_sample:
        verdict, reason = (
            ("dead", f"Мало вакансий: {sample} из {min_sample} за {window} дн. (inbox {inbox_n})")
            if age_days >= window
            else ("weak", f"Пока {sample} вакансий из {min_sample}, в inbox {inbox_n}. Окно ещё идёт.")
        )
    elif median is not None and median < bar:
        verdict, reason = "dead", f"Медианный match {median} ниже порога {bar} — сегмент не твой"
    elif outreach >= 5 and replies == 0 and inbox_alive:
        verdict, reason = (
            "weak",
            f"{outreach} касаний без ответа, но в inbox ещё {inbox_n} — рынок живой, молчит канал",
        )
    elif outreach >= 5 and replies == 0:
        verdict, reason = "dead", f"{outreach} касаний без ответа, inbox пуст. Канал или тезис не работают"
    elif outreach >= 2 and replies == 0:
        extra = f", в inbox {inbox_n}" if inbox_n else ""
        verdict, reason = "weak", f"{outreach} касаний, ответов нет{extra}. Ещё рано, но сигнал плохой"
    elif inbox_n and outreach == 0:
        verdict, reason = "alive", f"Сегмент живой: в inbox {inbox_n} вакансий, match не просел"
    else:
        verdict, reason = "alive", f"Сегмент живой: inbox {inbox_n}, воронка {outreach}, match не просел"

    return {
        "verdict": verdict,
        "reason": reason,
        "sample": sample,
        "inbox": inbox_n,
        "median_match": median,
        "nda_share": round(nda / sample, 2) if sample else 0,
        "fresh_24h": fresh,
        "outreach": outreach,
        "replies": replies,
        "age_days": age_days,
        "window_days": window,
        "salary_corridor": corridor_from_vacancies(rows),
    }


def rank_inbox_pack(rows: list[Vacancy]) -> list[Vacancy]:
    inbox = [row for row in rows if row.pipeline_stage == PipelineStage.INBOX]
    inbox.sort(
        key=lambda row: (
            0 if row.telegram_alias or row.contact_email or row.contact_phone else 1,
            -(row.match_score if row.match_score is not None else -1),
            -((row.created_at or row.published_at).timestamp() if (row.created_at or row.published_at) else 0),
        )
    )
    return inbox


async def refresh_thesis(session: AsyncSession, thesis: HuntThesis, *, commit: bool = True) -> dict:
    rows = await matching_vacancies(session, thesis)
    stats = evaluate(thesis, rows)
    thesis.last_verdict = stats["verdict"]
    thesis.last_reason = stats["reason"][:512]
    thesis.last_evaluated_at = _now()
    if commit:
        await session.commit()
    return stats


async def refresh_user_theses(session: AsyncSession, user_id: int | None, *, commit: bool = True) -> None:
    if not user_id:
        return
    rows = (
        await session.execute(
            select(HuntThesis).where(HuntThesis.user_id == user_id, HuntThesis.enabled.is_(True)).order_by(HuntThesis.id)
        )
    ).scalars().all()
    for thesis in rows:
        await refresh_thesis(session, thesis, commit=False)
    if commit and rows:
        await session.commit()
