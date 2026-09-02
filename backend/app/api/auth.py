from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.auth import (
    claim_orphans,
    clear_session_cookie,
    create_session,
    ensure_profile,
    hash_password,
    normalize_email,
    revoke_request_session,
    set_session_cookie,
    validate_credentials,
    verify_password,
)
from app.services.deps import can_view_others, get_current_user, require_host
from app.services.telegram_parse import backfill_user_telegram, ensure_user_telegram_pool

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    is_host: bool = False
    can_observe: bool = False


class ObserveIn(BaseModel):
    can_observe: bool


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        is_host=bool(user.is_host),
        can_observe=bool(user.is_host or user.can_observe),
    )


@router.post("/register", response_model=UserOut)
async def register(
    payload: AuthIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    email = validate_credentials(payload.email, payload.password)
    taken = (await session.execute(select(User.id).where(User.email == email))).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(409, "Этот email уже занят")
    is_first = (await session.execute(select(User.id).limit(1))).scalar_one_or_none() is None
    user = User(email=email, password_hash=hash_password(payload.password), is_host=is_first)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    if is_first:
        await claim_orphans(session, user.id)
    await ensure_profile(session, user)
    await backfill_user_telegram(session, user.id)
    token = await create_session(session, user.id)
    set_session_cookie(response, token)
    return _out(user)


@router.post("/login", response_model=UserOut)
async def login(
    payload: AuthIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    email = normalize_email(payload.email)
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    await ensure_user_telegram_pool(session, user.id)
    token = await create_session(session, user.id)
    set_session_cookie(response, token)
    return _out(user)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    await revoke_request_session(session, request)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _out(user)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> list[UserOut]:
    if not can_view_others(actor):
        raise HTTPException(403, "Список пользователей недоступен")
    rows = (await session.execute(select(User).order_by(User.id))).scalars().all()
    return [_out(row) for row in rows]


@router.patch("/users/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: int,
    payload: ObserveIn,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> UserOut:
    row = await session.get(User, user_id)
    if row is None:
        raise HTTPException(404, "Пользователь не найден")
    if row.is_host:
        raise HTTPException(400, "Хост и так видит всех")
    row.can_observe = bool(payload.can_observe)
    await session.commit()
    await session.refresh(row)
    return _out(row)
