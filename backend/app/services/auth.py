from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.auth_session import AuthSession
from app.models.scraper_config import ScraperConfig
from app.models.scraper_run import ScraperRun
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.vacancy import Vacancy

COOKIE_NAME = "hunt_session"
SESSION_DAYS = 30
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_credentials(email: str, password: str) -> str:
    cleaned = normalize_email(email)
    if not _EMAIL.match(cleaned):
        raise HTTPException(400, "Нужен нормальный email")
    if len(password) < 8:
        raise HTTPException(400, "Пароль — минимум 8 символов")
    return cleaned


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cookie_kwargs(*, max_age: int | None = None) -> dict:
    kwargs: dict = {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure(),
        "path": "/",
    }
    if max_age is not None:
        kwargs["max_age"] = max_age
    return kwargs


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        **cookie_kwargs(max_age=SESSION_DAYS * 24 * 60 * 60),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, **cookie_kwargs())


async def create_session(session: AsyncSession, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=_now() + timedelta(days=SESSION_DAYS),
            created_at=_now(),
        )
    )
    await session.commit()
    return token


async def user_from_request(session: AsyncSession, request: Request) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    row = (
        await session.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if row is None or row.expires_at < _now():
        return None
    return await session.get(User, row.user_id)


async def revoke_request_session(session: AsyncSession, request: Request) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return
    row = (
        await session.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.commit()


async def claim_orphans(session: AsyncSession, user_id: int) -> None:
    """First account on an old single-user DB inherits existing rows. Nobody else can."""
    taken = (await session.execute(select(Vacancy.user_id).where(Vacancy.user_id.is_not(None)).limit(1))).first()
    if taken is not None:
        return
    for model in (Vacancy, ScraperConfig, ScraperRun, UserProfile):
        await session.execute(update(model).where(model.user_id.is_(None)).values(user_id=user_id))


async def ensure_profile(session: AsyncSession, user: User) -> UserProfile:
    profile = (
        await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=user.id, display_name=user.email.split("@")[0])
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


async def upsert_google_user(session: AsyncSession, email: str, google_sub: str) -> tuple[User, bool]:
    sub = (google_sub or "").strip()
    if not sub:
        raise HTTPException(400, "Google не отдал аккаунт")
    cleaned = normalize_email(email)
    if not _EMAIL.match(cleaned):
        raise HTTPException(400, "Google не отдал email")
    existing = (await session.execute(select(User).where(User.google_sub == sub))).scalar_one_or_none()
    if existing is not None:
        if existing.email != cleaned:
            taken = (
                await session.execute(select(User.id).where(User.email == cleaned))
            ).scalar_one_or_none()
            if taken is not None and taken != existing.id:
                raise HTTPException(409, "Этот email уже занят")
            existing.email = cleaned
        return existing, False
    by_email = (await session.execute(select(User).where(User.email == cleaned))).scalar_one_or_none()
    if by_email is not None:
        if by_email.google_sub == sub:
            return by_email, False
        # Password (or other) account already owns this email. Auto-linking would
        # let anyone pre-register victim@x and later sit on the victim's Google login.
        raise HTTPException(409, "email-taken")
    is_first = (await session.execute(select(User.id).limit(1))).scalar_one_or_none() is None
    user = User(
        email=cleaned,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        google_sub=sub,
        is_host=is_first,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    if is_first:
        await claim_orphans(session, user.id)
    await ensure_profile(session, user)
    return user, True
