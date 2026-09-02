from __future__ import annotations

import asyncio
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode, urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.crypto import seal, unseal
from app.models.ping_slot import PingSlot
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.vacancy import NextStepKind, Vacancy
from app.models.vacancy_event import VacancyEvent
from app.services.auth import ensure_profile
from app.services.telegram import telegram_chat_url
from app.services.vacancy_events import display_labels, duration_minutes, event_end, list_events, refresh_next_step

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDARS_URL = "https://www.googleapis.com/calendar/v3/calendars"
CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPE = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/userinfo.email"
OAUTH_COOKIE = "hunt_google_oauth"
HUNT_CALENDAR_SUMMARY = "Hunt"
HUNT_CALENDAR_MARKER = "[hunt-crm]"
MEETING = re.compile(
    r"https?://[^\s<>'\"]+(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|telemost\.yandex|whereby\.com)",
    re.I,
)

KIND_LABEL = {
    "screening": "скрин",
    "interview": "собес",
    "offer_deadline": "оффер до",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def redirect_uri() -> str:
    return (settings.google_redirect_uri or "http://localhost:3000/api/google/callback").rstrip("/")


def settings_redirect(google: str) -> str:
    parsed = urlparse(redirect_uri())
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/settings?google={quote(google)}"


def client_credentials(profile: UserProfile) -> tuple[str, str]:
    client_id = (profile.google_client_id or settings.google_client_id or "").strip()
    client_secret = unseal(profile.google_client_secret) or (settings.google_client_secret or "").strip()
    return client_id, client_secret


def client_configured(profile: UserProfile) -> bool:
    client_id, client_secret = client_credentials(profile)
    return bool(client_id and client_secret)


def google_connected(profile: UserProfile) -> bool:
    return bool(profile.google_refresh_token)


def google_status(profile: UserProfile) -> dict:
    connected = google_connected(profile)
    ready = bool(profile.google_calendar_id)
    return {
        "connected": connected,
        "email": profile.google_email,
        "client_configured": client_configured(profile),
        "redirect_uri": redirect_uri(),
        "timezone": settings.google_calendar_timezone,
        "calendar_id": profile.google_calendar_id,
        "calendar_summary": HUNT_CALENDAR_SUMMARY,
        "calendar_ready": ready,
        "needs_reconnect": connected and not ready,
        "calendar_error": profile.google_calendar_error,
    }


def auth_url(profile: UserProfile, state: str) -> str:
    client_id, _secret = client_credentials(profile)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def new_oauth_state(user_id: int) -> str:
    return f"{user_id}:{secrets.token_urlsafe(24)}"


def parse_oauth_state(state: str) -> int | None:
    try:
        user_id, _nonce = state.split(":", 1)
        return int(user_id)
    except (ValueError, AttributeError):
        return None


def kind_label(kind: object) -> str:
    value = getattr(kind, "value", kind) or "interview"
    return KIND_LABEL.get(str(value), "собес")


def event_title(vacancy: Vacancy, label: str | None = None) -> str:
    company = (vacancy.company or "").strip() or "без компании"
    role = (vacancy.title or "").strip() or "вакансия"
    step = (label or "").strip() or kind_label(vacancy.next_step_kind)
    return f"{step} · {company} — {role}"


def event_location(vacancy: Vacancy) -> str | None:
    match = MEETING.search(vacancy.notes or "")
    if match:
        return match.group(0).rstrip("),.;")
    return telegram_chat_url(vacancy.telegram_alias)


def event_description(vacancy: Vacancy) -> str:
    lines = ["Hunt — следующий шаг"]
    if vacancy.source_url:
        lines.append(vacancy.source_url)
    chat = telegram_chat_url(vacancy.telegram_alias)
    if chat:
        lines.append(chat)
    notes = re.sub(r"\s+", " ", vacancy.notes or "").strip()
    if notes:
        lines.append(notes[:400])
    return "\n".join(lines)


def _event_body(vacancy: Vacancy, event: VacancyEvent, label: str | None = None) -> dict:
    start = event.starts_at.replace(microsecond=0)
    end = event_end(event).replace(microsecond=0)
    tz = settings.google_calendar_timezone
    body: dict = {
        "summary": event_title(vacancy, label),
        "description": event_description(vacancy),
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
        "extendedProperties": {
            "private": {
                "hunt_vacancy_id": str(vacancy.id),
                "hunt_event_id": str(event.id),
            }
        },
    }
    location = event_location(vacancy)
    if location:
        body["location"] = location
    return body


async def exchange_code(profile: UserProfile, code: str) -> dict:
    client_id, client_secret = client_credentials(profile)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(_google_error(response, "Не удалось обменять код Google"))
    return response.json()


async def _refresh(profile: UserProfile) -> None:
    client_id, client_secret = client_credentials(profile)
    if not profile.google_refresh_token:
        raise RuntimeError("Google не подключён")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "refresh_token": unseal(profile.google_refresh_token),
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code >= 400:
        profile.google_access_token = None
        raise RuntimeError("Сессия Google истекла — подключи календарь заново")
    data = response.json()
    profile.google_access_token = seal(data.get("access_token"))
    expires = int(data.get("expires_in") or 3600)
    profile.google_token_expires_at = _now() + timedelta(seconds=max(expires - 60, 30))


async def _access_token(profile: UserProfile) -> str:
    expires = profile.google_token_expires_at
    token = unseal(profile.google_access_token)
    if token and expires and expires > _now() + timedelta(seconds=30):
        return token
    await _refresh(profile)
    token = unseal(profile.google_access_token)
    if not token:
        raise RuntimeError("Нет токена Google")
    return token


async def fetch_email(access_token: str) -> str | None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    if response.status_code >= 400:
        return None
    return response.json().get("email")


def apply_tokens(profile: UserProfile, payload: dict) -> None:
    if payload.get("refresh_token"):
        profile.google_refresh_token = seal(payload["refresh_token"])
    profile.google_access_token = seal(payload.get("access_token"))
    expires = int(payload.get("expires_in") or 3600)
    profile.google_token_expires_at = _now() + timedelta(seconds=max(expires - 60, 30))


async def save_oauth(profile: UserProfile, payload: dict) -> None:
    apply_tokens(profile, payload)
    email = await fetch_email(unseal(profile.google_access_token) or "")
    if email:
        profile.google_email = email


def clear_oauth(profile: UserProfile) -> None:
    profile.google_refresh_token = None
    profile.google_access_token = None
    profile.google_token_expires_at = None
    profile.google_email = None
    profile.google_calendar_id = None
    profile.google_sync_token = None
    profile.google_calendar_error = None


def _google_error(response: httpx.Response, fallback: str) -> str:
    try:
        data = response.json()
        error = data.get("error_description") or data.get("error") or data.get("message")
        if isinstance(error, dict):
            error = error.get("message")
        if error:
            return str(error)
    except Exception:  # noqa: BLE001
        pass
    return fallback


def _events_url(calendar_id: str) -> str:
    return f"{CALENDARS_URL}/{quote(calendar_id, safe='')}/events"


def _minute(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(second=0, microsecond=0)


def google_wall_instant(event: dict, key: str) -> datetime | None:
    stamp = event.get(key) or {}
    raw = stamp.get("dateTime")
    if not raw:
        return None
    instant = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=ZoneInfo(settings.google_calendar_timezone))
    local = instant.astimezone(ZoneInfo(settings.google_calendar_timezone))
    return local.replace(tzinfo=None, second=0, microsecond=0)


def google_wall_start(event: dict) -> datetime | None:
    return google_wall_instant(event, "start")


async def _request(
    profile: UserProfile,
    method: str,
    url: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> httpx.Response:
    token = await _access_token(profile)
    kwargs: dict = {"headers": {"Authorization": f"Bearer {token}"}}
    if json is not None:
        kwargs["json"] = json
    if params is not None:
        kwargs["params"] = params
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(method, url, **kwargs)
    if response.status_code == 401:
        await _refresh(profile)
        kwargs["headers"] = {"Authorization": f"Bearer {unseal(profile.google_access_token) or ''}"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, url, **kwargs)
    return response


async def _upsert_event(profile: UserProfile, calendar_id: str, event_id: str | None, body: dict) -> str:
    url = _events_url(calendar_id)
    if event_id:
        response = await _request(profile, "PUT", f"{url}/{event_id}", json=body)
        if response.status_code == 404:
            event_id = None
            response = await _request(profile, "POST", url, json=body)
    else:
        response = await _request(profile, "POST", url, json=body)
    if response.status_code >= 400:
        raise RuntimeError(_google_error(response, "Google Calendar не принял событие"))
    return response.json().get("id") or event_id or ""


async def _delete_event(profile: UserProfile, calendar_id: str, event_id: str) -> None:
    response = await _request(profile, "DELETE", f"{_events_url(calendar_id)}/{event_id}")
    if response.status_code in {204, 404, 410}:
        return
    if response.status_code >= 400:
        raise RuntimeError(_google_error(response, "Не удалось удалить событие в Google"))


def _denied_calendar(response: httpx.Response) -> str | None:
    if response.status_code < 400:
        return None
    text = (response.text or "").lower()
    if response.status_code == 403 and (
        "accessnotconfigured" in text
        or "has not been used" in text
        or "is disabled" in text
        or "calendar-json.googleapis.com" in text
    ):
        return (
            "Включи Google Calendar API в том же проекте Cloud: APIs and services → Library → "
            "Google Calendar API → Enable. Потом нажми «Создать календарь Hunt»."
        )
    if response.status_code == 403 and ("insufficient" in text or "insufficientpermissions" in text):
        return "Токену не хватает права создать календарь Hunt. Нажми «Подключить ещё раз» — отключать не нужно."
    if response.status_code >= 400:
        return _google_error(response, "Google не дал доступ к календарю Hunt")
    return None


async def _find_hunt_calendar(profile: UserProfile) -> str | None:
    page: str | None = None
    while True:
        params: dict = {"maxResults": 100}
        if page:
            params["pageToken"] = page
        response = await _request(profile, "GET", CALENDAR_LIST_URL, params=params)
        if response.status_code >= 400:
            profile.google_calendar_error = _denied_calendar(response)
            return None
        profile.google_calendar_error = None
        data = response.json()
        for item in data.get("items") or []:
            if (item.get("summary") or "").strip() != HUNT_CALENDAR_SUMMARY:
                continue
            description = item.get("description") or ""
            if HUNT_CALENDAR_MARKER in description:
                return item.get("id")
        page = data.get("nextPageToken")
        if not page:
            return None


async def ensure_hunt_calendar(profile: UserProfile) -> str | None:
    if not google_connected(profile):
        return None
    if profile.google_calendar_id:
        return profile.google_calendar_id
    try:
        found = await _find_hunt_calendar(profile)
        if found:
            profile.google_calendar_id = found
            profile.google_calendar_error = None
            profile.google_sync_token = None
            return found
        if profile.google_calendar_error:
            return None
        response = await _request(
            profile,
            "POST",
            CALENDARS_URL,
            json={
                "summary": HUNT_CALENDAR_SUMMARY,
                "description": (
                    "Скрины, собесы, дедлайн оффера и пинг волны. Не воронка. "
                    f"{HUNT_CALENDAR_MARKER}"
                ),
                "timeZone": settings.google_calendar_timezone,
            },
        )
        if response.status_code >= 400:
            profile.google_calendar_error = _denied_calendar(response)
            return None
        calendar_id = (response.json() or {}).get("id")
        if not calendar_id:
            profile.google_calendar_error = "Google не вернул id календаря Hunt"
            return None
        profile.google_calendar_id = calendar_id
        profile.google_calendar_error = None
        profile.google_sync_token = None
        return calendar_id
    except Exception as exc:  # noqa: BLE001
        profile.google_calendar_error = str(exc)[:500]
        return None


async def _relocate_primary_leftovers(session: AsyncSession, user: User, profile: UserProfile) -> None:
    calendar_id = profile.google_calendar_id
    if not calendar_id:
        return
    events = (
        await session.execute(
            select(VacancyEvent).where(
                VacancyEvent.user_id == user.id,
                VacancyEvent.google_event_id.isnot(None),
            )
        )
    ).scalars().all()
    vacancy_ids = {row.vacancy_id for row in events}
    vacancies = {}
    if vacancy_ids:
        vacancies = {
            row.id: row
            for row in (
                await session.execute(select(Vacancy).where(Vacancy.id.in_(vacancy_ids)))
            ).scalars()
        }
    labels_by_vacancy: dict[int, dict[int, str]] = {}
    grouped: dict[int, list[VacancyEvent]] = {}
    for row in events:
        grouped.setdefault(row.vacancy_id, []).append(row)
    for vid, group in grouped.items():
        labels_by_vacancy[vid] = display_labels(group)
    for event in events:
        vacancy = vacancies.get(event.vacancy_id)
        old_id = event.google_event_id
        if not vacancy or not old_id:
            continue
        existing = await _request(profile, "GET", f"{_events_url(calendar_id)}/{old_id}")
        if existing.status_code == 200:
            continue
        try:
            label = (labels_by_vacancy.get(event.vacancy_id) or {}).get(event.id)
            event.google_event_id = await _upsert_event(profile, calendar_id, None, _event_body(vacancy, event, label))
            event.google_sync_error = None
            await _delete_event(profile, "primary", old_id)
        except Exception as exc:  # noqa: BLE001
            event.google_sync_error = str(exc)[:500]
        refresh_next_step(vacancy, grouped.get(event.vacancy_id) or [])
    slots = (
        await session.execute(select(PingSlot).where(PingSlot.user_id == user.id, PingSlot.google_event_id.isnot(None)))
    ).scalars().all()
    for slot in slots:
        old_id = slot.google_event_id
        if not old_id or slot.ping_at is None or slot.card_count <= 0:
            continue
        existing = await _request(profile, "GET", f"{_events_url(calendar_id)}/{old_id}")
        if existing.status_code == 200:
            continue
        try:
            slot.google_event_id = await _upsert_event(profile, calendar_id, None, _ping_event_body(slot))
            slot.google_sync_error = None
            slot.synced_count = slot.card_count
            slot.synced_ping_at = slot.ping_at
            await _delete_event(profile, "primary", old_id)
        except Exception as exc:  # noqa: BLE001
            slot.google_sync_error = str(exc)[:500]


async def _apply_google_event(session: AsyncSession, user: User, event: dict) -> None:
    props = (event.get("extendedProperties") or {}).get("private") or {}
    cancelled = event.get("status") == "cancelled"
    event_id = event.get("id")
    start = google_wall_instant(event, "start")
    end = google_wall_instant(event, "end")
    hunt_event_raw = props.get("hunt_event_id")
    vacancy_raw = props.get("hunt_vacancy_id")
    slot_raw = props.get("hunt_ping_slot_id")
    if hunt_event_raw or vacancy_raw:
        vacancy: Vacancy | None = None
        hunt_event: VacancyEvent | None = None
        if hunt_event_raw:
            try:
                hunt_event = await session.get(VacancyEvent, int(hunt_event_raw))
            except (TypeError, ValueError):
                hunt_event = None
            if hunt_event is not None:
                if hunt_event.user_id != user.id:
                    return
                vacancy = await session.get(Vacancy, hunt_event.vacancy_id)
        if vacancy is None and vacancy_raw:
            try:
                vacancy = await session.get(Vacancy, int(vacancy_raw))
            except (TypeError, ValueError):
                return
        if vacancy is None or vacancy.user_id != user.id:
            return
        rows = await list_events(session, vacancy.id)
        if hunt_event is None and event_id:
            hunt_event = next((row for row in rows if row.google_event_id == event_id), None)
        if hunt_event is None and len(rows) == 1:
            hunt_event = rows[0]
        if cancelled:
            if hunt_event is not None:
                await session.delete(hunt_event)
                await session.flush()
                refresh_next_step(vacancy, await list_events(session, vacancy.id))
            elif event_id and vacancy.google_event_id == event_id:
                vacancy.google_event_id = None
                vacancy.next_step_at = None
                vacancy.next_step_kind = None
            return
        if hunt_event is None and start:
            hunt_event = VacancyEvent(
                user_id=vacancy.user_id,
                vacancy_id=vacancy.id,
                kind=vacancy.next_step_kind or NextStepKind.INTERVIEW,
                starts_at=start,
                ends_at=end if end and end > start else start + timedelta(minutes=duration_minutes(vacancy.next_step_kind or NextStepKind.INTERVIEW)),
                google_event_id=event_id,
            )
            session.add(hunt_event)
            await session.flush()
        if hunt_event is None:
            return
        if event_id:
            hunt_event.google_event_id = event_id
        if start and _minute(hunt_event.starts_at) != start:
            span = event_end(hunt_event) - hunt_event.starts_at
            hunt_event.starts_at = start
            if not end:
                hunt_event.ends_at = start + span
        if end and end > hunt_event.starts_at and _minute(event_end(hunt_event)) != end:
            hunt_event.ends_at = end
        await session.flush()
        refresh_next_step(vacancy, await list_events(session, vacancy.id))
        return
    if not slot_raw:
        return
    try:
        slot = await session.get(PingSlot, int(slot_raw))
    except (TypeError, ValueError):
        return
    if slot is None or slot.user_id != user.id:
        return
    if cancelled:
        if event_id and slot.google_event_id == event_id:
            slot.google_event_id = None
        return
    if event_id:
        slot.google_event_id = event_id
    if start and _minute(slot.ping_at) != start:
        slot.ping_at = start
        slot.synced_ping_at = start
        slot.synced_count = slot.card_count


async def pull_hunt_events(session: AsyncSession, user: User, profile: UserProfile) -> None:
    if not google_connected(profile):
        return
    calendar_id = await ensure_hunt_calendar(profile)
    if not calendar_id:
        return
    fresh = profile.google_sync_token is None
    token = profile.google_sync_token
    items: list[dict] = []
    page: str | None = None
    retried = False
    while True:
        if token:
            params = {"syncToken": token}
        else:
            params = {"maxResults": "250", "singleEvents": "true", "showDeleted": "true"}
        if page:
            params["pageToken"] = page
        response = await _request(profile, "GET", _events_url(calendar_id), params=params)
        if response.status_code == 410:
            if retried:
                profile.google_calendar_error = "Синк календаря Hunt сброшен — открой воронку ещё раз"
                return
            retried = True
            profile.google_sync_token = None
            token = None
            page = None
            items = []
            fresh = True
            continue
        if response.status_code >= 400:
            profile.google_calendar_error = _google_error(response, "Не удалось прочитать календарь Hunt")
            return
        data = response.json()
        items.extend(data.get("items") or [])
        page = data.get("nextPageToken")
        if page:
            continue
        profile.google_sync_token = data.get("nextSyncToken") or token
        break
    for event in items:
        await _apply_google_event(session, user, event)
    if fresh:
        await _relocate_primary_leftovers(session, user, profile)
    profile.google_calendar_error = None
    await session.flush()


PULL_EVERY = timedelta(seconds=60)
_PULL_LOCKS: dict[int, asyncio.Lock] = {}
_LAST_PULL: dict[int, datetime] = {}


def _pull_lock(user_id: int) -> asyncio.Lock:
    lock = _PULL_LOCKS.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _PULL_LOCKS[user_id] = lock
    return lock


def mark_pulled(user_id: int, when: datetime | None = None) -> datetime:
    stamp = when or _now()
    _LAST_PULL[user_id] = stamp
    return stamp


async def pull_for_user(session: AsyncSession, user: User, *, force: bool = False) -> UserProfile:
    profile = await ensure_profile(session, user)
    if not google_connected(profile):
        return profile
    async with _pull_lock(user.id):
        last = _LAST_PULL.get(user.id)
        if not force and last and last > _now() - PULL_EVERY:
            return profile
        await session.refresh(profile)
        if (
            not force
            and profile.google_pulled_at
            and profile.google_pulled_at > _now() - PULL_EVERY
        ):
            mark_pulled(user.id, profile.google_pulled_at)
            return profile
        try:
            await pull_hunt_events(session, user, profile)
            profile.google_pulled_at = mark_pulled(user.id)
        except Exception as exc:  # noqa: BLE001
            profile.google_calendar_error = str(exc)[:500]
    return profile


async def _upsert_vacancy_google(
    profile: UserProfile,
    calendar_id: str,
    vacancy: Vacancy,
    event: VacancyEvent,
    label: str | None,
) -> None:
    event.google_event_id = await _upsert_event(
        profile,
        calendar_id,
        event.google_event_id,
        _event_body(vacancy, event, label),
    )
    event.google_sync_error = None


async def sync_one_vacancy_event(
    session: AsyncSession, profile: UserProfile, vacancy: Vacancy, event: VacancyEvent
) -> None:
    events = await list_events(session, vacancy.id)
    labels = display_labels(events)
    if not google_connected(profile):
        event.google_sync_error = None
        refresh_next_step(vacancy, events)
        return
    try:
        calendar_id = await ensure_hunt_calendar(profile)
        if not calendar_id:
            event.google_sync_error = profile.google_calendar_error or "Нет календаря Hunt"
            refresh_next_step(vacancy, events)
            await session.flush()
            return
        await _upsert_vacancy_google(profile, calendar_id, vacancy, event, labels.get(event.id))
        refresh_next_step(vacancy, await list_events(session, vacancy.id))
    except Exception as exc:  # noqa: BLE001
        event.google_sync_error = str(exc)[:500]
        refresh_next_step(vacancy, events)
    await session.flush()


async def sync_vacancy_event(session: AsyncSession, profile: UserProfile, vacancy: Vacancy) -> None:
    events = await list_events(session, vacancy.id)
    if not google_connected(profile):
        for row in events:
            row.google_sync_error = None
        vacancy.google_sync_error = None
        refresh_next_step(vacancy, events)
        return
    try:
        calendar_id = await ensure_hunt_calendar(profile)
        if not calendar_id:
            err = profile.google_calendar_error or "Нет календаря Hunt"
            for row in events:
                row.google_sync_error = err
            vacancy.google_sync_error = err
            refresh_next_step(vacancy, events)
            await session.flush()
            return
        labels = display_labels(events)
        seen: set[str] = set()
        for row in events:
            try:
                await _upsert_vacancy_google(profile, calendar_id, vacancy, row, labels.get(row.id))
                if row.google_event_id:
                    seen.add(row.google_event_id)
            except Exception as exc:  # noqa: BLE001
                row.google_sync_error = str(exc)[:500]
        leftover = vacancy.google_event_id
        if leftover and leftover not in seen:
            try:
                await _delete_event(profile, calendar_id, leftover)
            except Exception:  # noqa: BLE001
                pass
        refresh_next_step(vacancy, events)
    except Exception as exc:  # noqa: BLE001
        vacancy.google_sync_error = str(exc)[:500]
        for row in events:
            if not row.google_sync_error:
                row.google_sync_error = str(exc)[:500]
        refresh_next_step(vacancy, events)
    await session.flush()


async def delete_google_for_event(profile: UserProfile, event: VacancyEvent) -> None:
    if not google_connected(profile) or not event.google_event_id:
        return
    calendar_id = profile.google_calendar_id or await ensure_hunt_calendar(profile)
    if not calendar_id:
        return
    try:
        await _delete_event(profile, calendar_id, event.google_event_id)
    except Exception:  # noqa: BLE001
        pass
    event.google_event_id = None


def ping_event_title(label: str, count: int) -> str:
    name = (label or "").strip() or "без тезиса"
    return f"пинг волны · {name}, {_ru_cards(count)}"


def _ru_cards(n: int) -> str:
    n = abs(int(n))
    if n % 100 in {11, 12, 13, 14}:
        return f"{n} карточек"
    tail = n % 10
    if tail == 1:
        return f"{n} карточка"
    if tail in {2, 3, 4}:
        return f"{n} карточки"
    return f"{n} карточек"


def _ping_event_body(slot) -> dict:
    start = slot.ping_at
    assert start is not None
    start = start.replace(microsecond=0)
    end = start + timedelta(minutes=45)
    tz = settings.google_calendar_timezone
    ids = slot.vacancy_ids or []
    lines = [
        "Hunt — один слот пинга на пачку, не встреча на каждую карточку.",
        f"Карточек: {slot.card_count}",
    ]
    if ids:
        lines.append("id: " + ", ".join(str(i) for i in ids[:20]))
    return {
        "summary": ping_event_title(slot.label, slot.card_count),
        "description": "\n".join(lines),
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
        "extendedProperties": {"private": {"hunt_ping_slot_id": str(slot.id)}},
    }


async def sync_ping_slot(session: AsyncSession, profile: UserProfile, slot) -> None:
    if not google_connected(profile):
        slot.google_sync_error = None
        return
    try:
        calendar_id = await ensure_hunt_calendar(profile)
        if not calendar_id:
            slot.google_sync_error = profile.google_calendar_error or "Нет календаря Hunt"
            await session.flush()
            return
        if slot.ping_at is None or slot.card_count <= 0:
            if slot.google_event_id:
                await _delete_event(profile, calendar_id, slot.google_event_id)
                slot.google_event_id = None
            slot.google_sync_error = None
            slot.synced_count = 0
            await session.flush()
            return
        if (
            slot.google_event_id
            and not slot.google_sync_error
            and slot.synced_count == slot.card_count
            and slot.synced_ping_at == slot.ping_at
        ):
            await session.flush()
            return
        body = _ping_event_body(slot)
        slot.google_event_id = await _upsert_event(profile, calendar_id, slot.google_event_id, body)
        slot.google_sync_error = None
        slot.synced_count = slot.card_count
        slot.synced_ping_at = slot.ping_at
    except Exception as exc:  # noqa: BLE001
        slot.google_sync_error = str(exc)[:500]
    await session.flush()
