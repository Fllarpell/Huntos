from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.auth import cookie_kwargs, ensure_profile
from app.services.crypto import seal
from app.services.deps import require_host
from app.services.google_calendar import (
    OAUTH_COOKIE,
    auth_url,
    clear_oauth,
    client_configured,
    ensure_hunt_calendar,
    exchange_code,
    google_connected,
    google_status,
    new_oauth_state,
    parse_oauth_state,
    save_oauth,
    settings_redirect,
)

router = APIRouter(prefix="/api/google", tags=["google"])


class GoogleClientIn(BaseModel):
    google_client_id: str = ""
    google_client_secret: str = ""


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> dict:
    profile = await ensure_profile(session, user)
    return google_status(profile)


@router.put("/client")
async def save_client(
    payload: GoogleClientIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> dict:
    profile = await ensure_profile(session, user)
    client_id = payload.google_client_id.strip()
    secret = payload.google_client_secret.strip()
    if client_id:
        profile.google_client_id = client_id
    if secret:
        profile.google_client_secret = seal(secret)
    await session.commit()
    await session.refresh(profile)
    return google_status(profile)


@router.post("/connect")
async def connect(
    response: Response,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> dict:
    profile = await ensure_profile(session, user)
    if not client_configured(profile):
        raise HTTPException(
            400,
            "Сначала вставь Client ID и Secret из Google Cloud (OAuth Web client).",
        )
    state = new_oauth_state(user.id)
    response.set_cookie(
        OAUTH_COOKIE,
        state,
        **cookie_kwargs(max_age=600),
    )
    return {"url": auth_url(profile, state)}


@router.get("/callback")
async def callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    def bounce(message: str) -> RedirectResponse:
        redirect = RedirectResponse(settings_redirect(message), status_code=302)
        redirect.delete_cookie(OAUTH_COOKIE, **cookie_kwargs())
        return redirect

    if error:
        return bounce(error)
    cookie_state = request.cookies.get(OAUTH_COOKIE)
    if not code or not state or not cookie_state or state != cookie_state:
        return bounce("oauth-mismatch")
    user_id = parse_oauth_state(state)
    if user_id is None:
        return bounce("oauth-state")
    user = await session.get(User, user_id)
    if user is None:
        return bounce("no-user")
    profile = await ensure_profile(session, user)
    try:
        tokens = await exchange_code(profile, code)
        await save_oauth(profile, tokens)
        if not profile.google_refresh_token:
            await session.commit()
            return bounce("no-refresh")
        await ensure_hunt_calendar(profile)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return bounce(str(exc)[:120])
    redirect = RedirectResponse(settings_redirect("ok"), status_code=302)
    redirect.delete_cookie(OAUTH_COOKIE, **cookie_kwargs())
    return redirect


@router.post("/disconnect")
async def disconnect(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> dict:
    profile = await ensure_profile(session, user)
    clear_oauth(profile)
    await session.commit()
    await session.refresh(profile)
    return google_status(profile)


@router.post("/calendar")
async def create_hunt_calendar(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> dict:
    profile = await ensure_profile(session, user)
    if not google_connected(profile):
        raise HTTPException(400, "Сначала подключи Google")
    await ensure_hunt_calendar(profile)
    await session.commit()
    await session.refresh(profile)
    status = google_status(profile)
    if not status["calendar_ready"]:
        raise HTTPException(400, status["calendar_error"] or "Календарь Hunt не создался")
    return status
