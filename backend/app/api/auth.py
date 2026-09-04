from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.auth import (
    claim_orphans,
    clear_session_cookie,
    cookie_kwargs,
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
from app.services.google_calendar import (
    OAUTH_CALLBACK_COOKIE,
    OAUTH_COOKIE,
    auth_url,
    callback_uri_from_headers,
    new_login_state,
    resolved_client_credentials,
)
from app.services.telegram_parse import backfill_user_telegram, ensure_user_telegram_pool

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    id: int
    email: str
    is_host: bool | None = None
    can_observe: bool | None = None


class ObserveIn(BaseModel):
    can_observe: bool


def _out(user: User, *, staff: bool = False) -> UserOut:
    if user.is_host:
        return UserOut(id=user.id, email=user.email, is_host=True, can_observe=True)
    if staff or user.can_observe:
        return UserOut(id=user.id, email=user.email, can_observe=bool(user.can_observe))
    return UserOut(id=user.id, email=user.email)


@router.post("/register", response_model=UserOut, response_model_exclude_none=True)
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


@router.post("/login", response_model=UserOut, response_model_exclude_none=True)
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


@router.get("/me", response_model=UserOut, response_model_exclude_none=True)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _out(user)


@router.get("/google")
async def google_available(session: AsyncSession = Depends(get_session)) -> dict:
    client_id, client_secret = await resolved_client_credentials(session)
    return {"available": bool(client_id and client_secret)}


@router.post("/google")
async def google_login_start(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    client_id, client_secret = await resolved_client_credentials(session)
    if not client_id or not client_secret:
        raise HTTPException(400, "Google вход пока недоступен")
    state = new_login_state()
    callback = callback_uri_from_headers(request.headers)
    kwargs = cookie_kwargs(max_age=600)
    response.set_cookie(OAUTH_COOKIE, state, **kwargs)
    response.set_cookie(OAUTH_CALLBACK_COOKIE, callback, **kwargs)
    return {"url": auth_url(client_id, state, callback)}


@router.get("/users", response_model=list[UserOut], response_model_exclude_none=True)
async def list_users(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> list[UserOut]:
    if not can_view_others(actor):
        raise HTTPException(404, "Не найдено")
    rows = (await session.execute(select(User).order_by(User.id))).scalars().all()
    return [_out(row, staff=actor.is_host) for row in rows]


@router.patch("/users/{user_id}", response_model=UserOut, response_model_exclude_none=True)
async def patch_user(
    user_id: int,
    payload: ObserveIn,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> UserOut:
    row = await session.get(User, user_id)
    if row is None or row.is_host:
        raise HTTPException(404, "Не найдено")
    row.can_observe = bool(payload.can_observe)
    await session.commit()
    await session.refresh(row)
    return _out(row, staff=True)
