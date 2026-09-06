from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.user_profile import UserProfile
from app.models.vacancy import ScoringStatus, Vacancy
from app.prompts.scoring import (
    ADAPT_SYSTEM,
    ADAPT_USER,
    COVER_LETTER_SYSTEM,
    COVER_LETTER_USER,
    HH_LETTER_SYSTEM,
    HH_LETTER_USER,
    SCORING_SYSTEM,
    SCORING_USER,
    TELEGRAM_DRAFT_SYSTEM,
    TELEGRAM_DRAFT_USER,
)
from app.services.scoring.llm import LLMError, complete, config_from_profile, extract_json
from app.services.resume import merge_adapted_experience, normalize_resume, resume_for_llm


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
    resume = resume_for_llm(profile)
    if not resume.strip():
        vacancy.scoring_status = ScoringStatus.SKIPPED
        vacancy.match_rationale = {"summary": "Заполни резюме в разделе «резюме», чтобы считать Fit."}
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
    resume = resume_for_llm(profile)
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
                "summary": "Заполни резюме в разделе «резюме», чтобы считать Fit."
            }
        await session.commit()
        return vacancies

    scored: list[Vacancy] = []
    for vacancy in vacancies:
        scored.append(await score_vacancy(session, vacancy))
    return scored


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


async def adapt_resume(session: AsyncSession, vacancy: Vacancy) -> dict:
    profile = await get_profile(session, vacancy.user_id)
    resume = resume_for_llm(profile)
    if not resume.strip():
        raise LLMError("Сначала заполни резюме")
    base = normalize_resume(getattr(profile, "resume_json", None))
    if not any(job["company"] or job["title"] or job["bullets"] for job in base["experience"]):
        raise LLMError("В резюме нет опыта — разбери PDF или заполни места работы")
    cfg = config_from_profile(profile)
    fields = _vacancy_prompt_fields(vacancy)
    raw = await complete(
        cfg,
        system=ADAPT_SYSTEM,
        user=ADAPT_USER.format(
            resume=resume[:12000],
            experience_json=json.dumps(base["experience"], ensure_ascii=False)[:12000],
            rationale=str(vacancy.match_rationale or {}),
            title=fields["title"],
            company=fields["company"],
            skills=fields["skills"],
            requirements=fields["requirements"],
            description=fields["description"],
        ),
        json_mode=True,
    )
    data = extract_json(raw)
    merged = merge_adapted_experience(base, data.get("experience"))
    vacancy.adaptation_advice = {
        "missing_skills": _string_list(data.get("missing_skills")),
        "do_not_invent": _string_list(data.get("do_not_invent")),
        "experience": merged["experience"],
        "previous_experience": base["experience"],
    }
    flag_modified(vacancy, "adaptation_advice")
    await session.commit()
    return vacancy.adaptation_advice


async def generate_cover_letter(session: AsyncSession, vacancy: Vacancy) -> str:
    profile = await get_profile(session, vacancy.user_id)
    resume = resume_for_llm(profile)
    if not resume.strip():
        raise LLMError("Сначала заполни резюме")
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


async def generate_hh_letter(session: AsyncSession, vacancy: Vacancy, *, profile_url: str) -> str:
    profile = await get_profile(session, vacancy.user_id)
    resume = resume_for_llm(profile)
    if not resume.strip():
        raise LLMError("Сначала заполни резюме")
    fields = _vacancy_prompt_fields(vacancy)
    cfg = config_from_profile(profile)
    text = await complete(
        cfg,
        system=HH_LETTER_SYSTEM,
        user=HH_LETTER_USER.format(
            resume=resume[:8000],
            title=fields["title"],
            company=fields["company"],
            skills=fields["skills"],
            requirements=fields["requirements"],
        ),
        json_mode=False,
    )
    body = text.strip()
    if profile_url:
        body = f"{body}\n\nАдаптированное резюме: {profile_url}"
    vacancy.cover_letter = body
    await session.commit()
    return body


async def generate_telegram_draft(session: AsyncSession, vacancy: Vacancy) -> str:
    profile = await get_profile(session, vacancy.user_id)
    resume = resume_for_llm(profile)
    if not resume.strip():
        raise LLMError("Сначала заполни резюме")
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
