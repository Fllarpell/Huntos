from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.hunt_thesis import HuntThesis
from app.models.user import User
from app.services.deps import get_scope_user
from app.services.salary_market import build_salary_market, refresh_salary_benchmarks
from app.services.thesis import matching_vacancies

router = APIRouter(prefix="/api/salary-market", tags=["salary-market"])


@router.get("")
async def salary_market(
    hunt_id: int | None = Query(None),
    grade: str | None = Query(None),
    specialty: str | None = Query(None),
    refresh: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    sample_rows = None
    if hunt_id is not None:
        thesis = (
            await session.execute(
                select(HuntThesis).where(HuntThesis.id == hunt_id, HuntThesis.user_id == user.id)
            )
        ).scalar_one_or_none()
        if thesis is not None:
            sample_rows = await matching_vacancies(session, thesis)
    return await build_salary_market(
        session,
        user.id,
        sample_rows=sample_rows,
        grade=grade,
        specialty=specialty,
        refresh_levels=refresh,
    )


@router.post("/levels/refresh")
async def levels_refresh(user: User = Depends(get_scope_user)) -> dict:
    _ = user
    return await refresh_salary_benchmarks()
