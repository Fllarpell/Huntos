from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import UserProfile
from app.models.vacancy import ScoringStatus, Vacancy
from app.prompts.scoring import (
    ADAPT_SYSTEM,
    ADAPT_USER,
    COVER_LETTER_SYSTEM,
    COVER_LETTER_USER,
    SCORING_SYSTEM,
    SCORING_USER,
    TELEGRAM_DRAFT_SYSTEM,
    TELEGRAM_DRAFT_USER,
)
from app.services.scoring.llm import LLMError, complete, config_from_profile, extract_json


def _vacancy_prompt_fields(vacancy: Vacancy) -> dict:
    return {
        "title": vacancy.title,
        "company": vacancy.company or "",
        "grade": vacancy.grade or "",
        "work_format": vacancy.work_format or "",
        "salary": vacancy.salary_raw or "не указана",
        "skills": ", ".join(vacancy.skills or []),
        "requirements": (vacancy.requirements or "")[:6000],
        "description": (vacancy.description or "")[:6000],
    }


async def get_profile(session: AsyncSession, user_id: int | None) -> UserProfile | None:
    if not user_id:
        return None
    return (
        await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    ).scalar_one_or_none()


async def score_vacancy(session: AsyncSession, vacancy: Vacancy) -> Vacancy:
    profile = await get_profile(session, vacancy.user_id)
    resume = (profile.resume_text if profile else None) or ""
    if not resume.strip():
        vacancy.scoring_status = ScoringStatus.SKIPPED
        vacancy.match_rationale = {"summary": "Загрузите базовое резюме в Настройках, чтобы считать Match Score."}
        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    cfg = config_from_profile(profile)
    try:
        raw = await complete(
            cfg,
            system=SCORING_SYSTEM,
            user=SCORING_USER.format(resume=resume[:12000], **_vacancy_prompt_fields(vacancy)),
            json_mode=True,
        )
        data = extract_json(raw)
        score = int(data.get("match_score", 0))
        vacancy.match_score = max(0, min(100, score))
        vacancy.match_rationale = data
        vacancy.scoring_status = ScoringStatus.SCORED
    except Exception as exc:  # noqa: BLE001
        vacancy.scoring_status = ScoringStatus.ERROR
        vacancy.match_rationale = {"summary": f"Ошибка скоринга: {exc}"}
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


async def score_pending(session: AsyncSession, *, user_id: int, limit: int = 10) -> list[Vacancy]:
    profile = await get_profile(session, user_id)
    resume = (profile.resume_text if profile else None) or ""
    result = await session.execute(
        select(Vacancy)
        .where(
            Vacancy.user_id == user_id,
            Vacancy.scoring_status == ScoringStatus.PENDING,
            Vacancy.duplicate_of_id.is_(None),
        )
        .order_by(Vacancy.published_at.desc())
        .limit(limit)
    )
    vacancies = list(result.scalars().all())
    if not resume.strip():
        for vacancy in vacancies:
            vacancy.scoring_status = ScoringStatus.SKIPPED
            vacancy.match_rationale = {
                "summary": "Загрузите базовое резюме в Настройках, чтобы считать Match Score."
            }
        await session.commit()
        return vacancies

    scored: list[Vacancy] = []
    for vacancy in vacancies:
        scored.append(await score_vacancy(session, vacancy))
    return scored


async def adapt_resume(session: AsyncSession, vacancy: Vacancy) -> dict:
    profile = await get_profile(session, vacancy.user_id)
    resume = (profile.resume_text if profile else None) or ""
    if not resume.strip():
        raise LLMError("Сначала загрузите резюме в Настройках")
    cfg = config_from_profile(profile)
    raw = await complete(
        cfg,
        system=ADAPT_SYSTEM,
        user=ADAPT_USER.format(
            resume=resume[:12000],
            rationale=str(vacancy.match_rationale or {}),
            **_vacancy_prompt_fields(vacancy),
        ),
        json_mode=True,
    )
    data = extract_json(raw)
    vacancy.adaptation_advice = data
    await session.commit()
    return data


async def generate_cover_letter(session: AsyncSession, vacancy: Vacancy) -> str:
    profile = await get_profile(session, vacancy.user_id)
    resume = (profile.resume_text if profile else None) or ""
    if not resume.strip():
        raise LLMError("Сначала загрузите резюме в Настройках")
    cfg = config_from_profile(profile)
    text = await complete(
        cfg,
        system=COVER_LETTER_SYSTEM,
        user=COVER_LETTER_USER.format(resume=resume[:12000], **_vacancy_prompt_fields(vacancy)),
        json_mode=False,
    )
    vacancy.cover_letter = text.strip()
    await session.commit()
    return vacancy.cover_letter


async def generate_telegram_draft(session: AsyncSession, vacancy: Vacancy) -> str:
    profile = await get_profile(session, vacancy.user_id)
    resume = (profile.resume_text if profile else None) or ""
    if not resume.strip():
        raise LLMError("Сначала загрузите резюме в Настройках")
    rationale = vacancy.match_rationale or {}
    cfg = config_from_profile(profile)
    text = await complete(
        cfg,
        system=TELEGRAM_DRAFT_SYSTEM,
        user=TELEGRAM_DRAFT_USER.format(
            resume=resume[:8000],
            strengths=", ".join(rationale.get("strengths") or []) or "—",
            gaps=", ".join(rationale.get("gaps") or []) or "—",
            **_vacancy_prompt_fields(vacancy),
        ),
        json_mode=False,
    )
    vacancy.telegram_message = text.strip()
    await session.commit()
    return vacancy.telegram_message
