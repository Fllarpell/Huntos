from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm.attributes import flag_modified

from app.db import get_session
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.dto import ProfileOut, ProfileUpdate
from app.services.crypto import seal
from app.services.auth import ensure_profile
from app.services.custom_fields import normalize_defs
from app.services.deps import get_scope_user
from app.services.google_calendar import google_status, ensure_hunt_calendar
from app.services.hunts import hunt_field_defs, list_hunts, maybe_hunt, save_hunt_fields
from app.services.scheduler import sync_jobs

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_out(profile: UserProfile, hunt_fields: list | None = None) -> ProfileOut:
    data = ProfileOut.model_validate(profile)
    data.openai_api_key_set = bool(profile.openai_api_key)
    status = google_status(profile)
    data.google_connected = status["connected"]
    data.google_email = status["email"]
    data.google_client_id_set = status["client_configured"]
    data.google_redirect_uri = status["redirect_uri"]
    data.google_calendar_ready = bool(status.get("calendar_ready"))
    data.google_needs_reconnect = bool(status.get("needs_reconnect"))
    data.google_calendar_error = status.get("calendar_error")
    data.custom_fields = hunt_fields if hunt_fields is not None else normalize_defs(profile.custom_fields, strict=False)
    return data


async def _profile_fields(session: AsyncSession, user: User, profile: UserProfile) -> list:
    hunt = await maybe_hunt(session, user, profile.active_hunt_id)
    if hunt is not None:
        return hunt_field_defs(hunt, profile)
    hunts = await list_hunts(session, user)
    if len(hunts) == 1:
        return hunt_field_defs(hunts[0], profile)
    return hunt_field_defs(None, profile)


@router.get("/profile", response_model=ProfileOut)
async def read_profile(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ProfileOut:
    profile = await ensure_profile(session, user)
    if google_status(profile)["connected"] and not profile.google_calendar_id:
        await ensure_hunt_calendar(profile)
        await session.commit()
        await session.refresh(profile)
    return _to_out(profile, await _profile_fields(session, user, profile))


@router.put("/profile", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ProfileOut:
    profile = await ensure_profile(session, user)
    data = payload.model_dump(exclude_unset=True)
    if "custom_fields" in data:
        raw = data.pop("custom_fields")
        hunt = await maybe_hunt(session, user, profile.active_hunt_id)
        if hunt is None:
            hunts = await list_hunts(session, user)
            hunt = hunts[0] if len(hunts) == 1 else None
        try:
            if hunt is not None:
                await save_hunt_fields(session, hunt, raw)
            else:
                profile.custom_fields = normalize_defs(raw)
                flag_modified(profile, "custom_fields")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    for key, value in data.items():
        if key in {"openai_api_key", "google_client_id", "google_client_secret"} and value == "":
            continue
        if key in {"openai_api_key", "google_client_secret"} and isinstance(value, str):
            value = seal(value)
        setattr(profile, key, value)
    await session.commit()
    await session.refresh(profile)
    await sync_jobs()
    return _to_out(profile, await _profile_fields(session, user, profile))


@router.post("/profile/resume", response_model=ProfileOut)
async def upload_resume(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ProfileOut:
    profile = await ensure_profile(session, user)
    raw = await file.read()
    name = file.filename or "resume.txt"
    if name.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"Не удалось прочитать PDF: {exc}") from exc
    else:
        text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise HTTPException(400, "Файл пустой или текст не извлечён")
    profile.resume_text = text
    profile.resume_filename = name
    await session.commit()
    await session.refresh(profile)
    return _to_out(profile, await _profile_fields(session, user, profile))
