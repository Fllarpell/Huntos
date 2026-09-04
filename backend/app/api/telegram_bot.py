from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.deps import get_current_user, require_host
from app.services.telegram_bot import (
    apply_prefs,
    bind_status,
    ensure_bind,
    get_state,
    hydrate_bot_username,
    issue_link,
    save_bot_token,
    unlink,
)

router = APIRouter(prefix="/api/telegram/bot", tags=["telegram-bot"])


class BotTokenIn(BaseModel):
    token: str = ""


class BotPrefsIn(BaseModel):
    want_vacancies: bool | None = None
    want_internships: bool | None = None
    want_hackathons: bool | None = None
    want_steps: bool | None = None
    want_ping: bool | None = None


@router.get("")
async def bot_status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    state = await hydrate_bot_username(session, await get_state(session))
    row = await ensure_bind(session, user.id)
    return bind_status(state, row)


@router.post("/link")
async def bot_link(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return await issue_link(session, user)
    except RuntimeError:
        raise HTTPException(400, "Telegram-бот пока недоступен") from None


@router.post("/unlink")
async def bot_unlink(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    state = await get_state(session)
    row = await ensure_bind(session, user.id)
    await unlink(session, row)
    await session.refresh(row)
    return bind_status(state, row)


@router.put("/prefs")
async def bot_prefs(
    payload: BotPrefsIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    state = await get_state(session)
    row = await ensure_bind(session, user.id)
    await apply_prefs(row, payload.model_dump(exclude_unset=True))
    await session.commit()
    await session.refresh(row)
    return bind_status(state, row)


@router.put("/token")
async def bot_save_token(
    payload: BotTokenIn,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> dict:
    token = payload.token.strip()
    if not token:
        raise HTTPException(400, "Нужен токен бота")
    try:
        await save_bot_token(session, token)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    state = await get_state(session)
    return {"available": True, "username": state.bot_username}
