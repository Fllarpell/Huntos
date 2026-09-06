from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user_profile import UserProfile
from app.models.vacancy import Vacancy
from app.services.resume import merge_adapted_experience, normalize_resume, resume_is_empty

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/cv/{share_id}")
async def public_cv(
    share_id: str,
    target: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    token = (share_id or "").strip()
    if not token:
        raise HTTPException(404, "Резюме не опубликовано")
    profile = (
        await session.execute(
            select(UserProfile).where(
                UserProfile.resume_share_id == token,
                UserProfile.resume_public.is_(True),
            )
        )
    ).scalar_one_or_none()
    if profile is None or resume_is_empty(profile.resume_json):
        raise HTTPException(404, "Резюме не опубликовано")
    doc = normalize_resume(profile.resume_json)
    adapted = False
    if target:
        vacancy = await session.get(Vacancy, target)
        if vacancy is not None and vacancy.user_id == profile.user_id:
            experience = (vacancy.adaptation_advice or {}).get("experience")
            if experience:
                doc = merge_adapted_experience(doc, experience)
                adapted = True
    return {"resume": doc, "adapted": adapted}
