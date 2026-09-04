import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.feedback import FeedbackNote
from app.models.user import User
from app.services.deps import get_current_user, require_host
from app.services.feedback_notify import notify_feedback

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])

KINDS = {"bug", "idea"}


class FeedbackIn(BaseModel):
    kind: str
    body: str = Field(min_length=8, max_length=4000)
    page: str | None = Field(default=None, max_length=256)
    contact_name: str | None = Field(default=None, max_length=128)
    reply_to: str | None = Field(default=None, max_length=256)


class FeedbackOut(BaseModel):
    id: int
    kind: str
    body: str
    page: str | None = None
    contact_name: str | None = None
    reply_to: str | None = None
    email: str
    created_at: datetime


def _clean(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return text[:limit]


@router.post("", status_code=200)
async def create_feedback(
    payload: FeedbackIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    kind = payload.kind.strip()
    if kind not in KINDS:
        raise HTTPException(400, "Непонятный тип")
    body = payload.body.strip()
    if len(body) < 8:
        raise HTTPException(400, "Напиши чуть подробнее")
    page = _clean(payload.page, 256)
    contact_name = _clean(payload.contact_name, 128)
    reply_to = _clean(payload.reply_to, 256)
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(
        FeedbackNote(
            user_id=user.id,
            kind=kind,
            body=body,
            page=page,
            contact_name=contact_name,
            reply_to=reply_to,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    try:
        await notify_feedback(
            session,
            kind=kind,
            body=body,
            email=user.email,
            page=page,
            contact_name=contact_name,
            reply_to=reply_to,
        )
    except Exception:
        log.exception("feedback notify failed")
    return {"ok": True}


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> list[FeedbackOut]:
    rows = (
        await session.execute(
            select(FeedbackNote, User.email)
            .join(User, User.id == FeedbackNote.user_id)
            .order_by(FeedbackNote.id.desc())
        )
    ).all()
    return [
        FeedbackOut(
            id=note.id,
            kind=note.kind,
            body=note.body,
            page=note.page,
            contact_name=note.contact_name,
            reply_to=note.reply_to,
            email=email,
            created_at=note.created_at,
        )
        for note, email in rows
    ]
