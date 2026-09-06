from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.deps import get_scope_user
from app.services.onboarding import onboarding_status, seed_from_resume

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    return await onboarding_status(session, user)


@router.post("/seed")
async def seed(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    return await seed_from_resume(session, user)
