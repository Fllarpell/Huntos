from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.auth import (
    cookie_kwargs,
    create_session,
    ensure_profile,
    set_session_cookie,
    upsert_google_user,
    user_from_request,
)
from app.services.crypto import seal, unseal
from app.services.deps import get_current_user, require_host
from app.services.google_calendar import (
    OAUTH_CALLBACK_COOKIE,
    OAUTH_COOKIE,
    auth_url,
    callback_uri_from_headers,
    clear_oauth,
    ensure_hunt_calendar,
    exchange_code,
    fetch_userinfo,
    google_connected,
    google_status,
    home_redirect,
    login_redirect,
    new_oauth_state,
    origin_of,
    parse_oauth_intent,
    resolved_callback,
    resolved_client_credentials,
    save_oauth,
    settings_redirect,
    stamp_app_client,
)
from app.services.telegram_parse import backfill_user_telegram, ensure_user_telegram_pool

router = APIRouter(prefix="/api/google", tags=["google"])


class GoogleClientIn(BaseModel):
    google_client_id: str = ""
    google_client_secret: str = ""


async def _status_for(session: AsyncSession, user: User) -> dict:
    profile = await ensure_profile(session, user)
    client_id, client_secret = await resolved_client_credentials(session, profile)
    return google_status(profile, app_configured=bool(client_id and client_secret))


@router.get("/status")
async def status(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    data = await _status_for(session, user)
    data["redirect_uri"] = callback_uri_from_headers(request.headers)
    return data


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
    return await _status_for(session, user)


@router.post("/connect")
async def connect(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    profile = await ensure_profile(session, user)
    client_id, client_secret = await resolved_client_credentials(session, profile)
    if not client_id or not client_secret:
        raise HTTPException(400, "Google пока недоступен")
    state = new_oauth_state(user.id)
    callback = callback_uri_from_headers(request.headers)
    kwargs = cookie_kwargs(max_age=600)
    response.set_cookie(
        OAUTH_COOKIE,
        state,
        **kwargs,
    )
    response.set_cookie(OAUTH_CALLBACK_COOKIE, callback, **kwargs)
    return {"url": auth_url(client_id, state, callback)}


@router.get("/callback")
async def callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    cookie_state = request.cookies.get(OAUTH_COOKIE)
    intent, user_id = parse_oauth_intent(state or "")
    login = intent == "login"
    callback = resolved_callback(request.cookies.get(OAUTH_CALLBACK_COOKIE) or callback_uri_from_headers(request.headers))
    origin = origin_of(callback)

    def bounce(message: str) -> RedirectResponse:
        target = login_redirect(message, origin) if login else settings_redirect(message, origin)
        redirect = RedirectResponse(target, status_code=302)
        redirect.delete_cookie(OAUTH_COOKIE, **cookie_kwargs())
        redirect.delete_cookie(OAUTH_CALLBACK_COOKIE, **cookie_kwargs())
        return redirect

    if error:
        return bounce(error)
    if not code or not state or not cookie_state or state != cookie_state:
        return bounce("oauth-mismatch")
    if intent not in {"login", "calendar"}:
        return bounce("oauth-state")

    try:
        if login:
            client_id, client_secret = await resolved_client_credentials(session)
            if not client_id or not client_secret:
                return bounce("oauth-state")
            tokens = await exchange_code(code, client_id, client_secret, callback)
            info = await fetch_userinfo(str(tokens.get("access_token") or ""))
            google_sub = str(info.get("id") or "").strip()
            email = str(info.get("email") or "").strip()
            verified = info.get("verified_email") is True or info.get("email_verified") is True
            if not verified:
                return bounce("unverified-email")
            user, created = await upsert_google_user(session, email, google_sub)
            if created:
                await backfill_user_telegram(session, user.id)
            else:
                await ensure_user_telegram_pool(session, user.id)
            profile = await ensure_profile(session, user)
            stamp_app_client(profile, client_id, client_secret)
            await save_oauth(profile, tokens)
            if not profile.google_refresh_token:
                await session.commit()
                return bounce("no-refresh")
            await ensure_hunt_calendar(profile)
            await session.commit()
            token = await create_session(session, user.id)
            redirect = RedirectResponse(home_redirect(fresh=created, origin=origin), status_code=302)
            set_session_cookie(redirect, token)
            redirect.delete_cookie(OAUTH_COOKIE, **cookie_kwargs())
            redirect.delete_cookie(OAUTH_CALLBACK_COOKIE, **cookie_kwargs())
            return redirect

        if user_id is None:
            return bounce("oauth-state")
        user = await session.get(User, user_id)
        actor = await user_from_request(session, request)
        if user is None or actor is None or actor.id != user.id:
            return bounce("no-user")
        profile = await ensure_profile(session, user)
        client_id, client_secret = await resolved_client_credentials(session, profile)
        if not client_id or not client_secret:
            return bounce("oauth-state")
        tokens = await exchange_code(code, client_id, client_secret, callback)
        stamp_app_client(profile, client_id, client_secret)
        await save_oauth(profile, tokens)
        info = await fetch_userinfo(unseal(profile.google_access_token) or "")
        google_sub = str(info.get("id") or "").strip()
        if google_sub and not user.google_sub:
            user.google_sub = google_sub
        if not profile.google_refresh_token:
            await session.commit()
            return bounce("no-refresh")
        await ensure_hunt_calendar(profile)
        await session.commit()
    except HTTPException as exc:
        return bounce(str(exc.detail)[:120])
    except Exception as exc:  # noqa: BLE001
        return bounce(str(exc)[:120])
    redirect = RedirectResponse(settings_redirect("ok", origin), status_code=302)
    redirect.delete_cookie(OAUTH_COOKIE, **cookie_kwargs())
    redirect.delete_cookie(OAUTH_CALLBACK_COOKIE, **cookie_kwargs())
    return redirect


@router.post("/disconnect")
async def disconnect(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    profile = await ensure_profile(session, user)
    clear_oauth(profile)
    await session.commit()
    await session.refresh(profile)
    return await _status_for(session, user)


@router.post("/calendar")
async def create_hunt_calendar(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    profile = await ensure_profile(session, user)
    if not google_connected(profile):
        raise HTTPException(400, "Сначала подключи Google")
    await ensure_hunt_calendar(profile)
    await session.commit()
    await session.refresh(profile)
    status = await _status_for(session, user)
    if not status["calendar_ready"]:
        raise HTTPException(400, status["calendar_error"] or "Календарь HuntOS не создался")
    return status
