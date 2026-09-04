"""Per-user Telegram Bot API. Outbound digests/reminders + /start bind.

Host Telethon scrape stays in telegram_host.py. This bot never shares one chat
across Hunt accounts.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.models.hackathon_event import HackathonEvent
from app.models.internship_monitor import InternshipMonitor
from app.models.telegram_bot import TelegramBotBind, TelegramBotState, TelegramLinkToken, TelegramNotice
from app.models.user import User
from app.models.vacancy import PipelineStage, Vacancy
from app.models.vacancy_event import VacancyEvent
from app.services.crypto import seal, unseal
from app.services.google_calendar import public_origin
from app.services.hackathons_sync import compute_is_new
from app.services.internship_catalog import programs
from app.services.nudge import ping_due, silence_days
from app.services.telegram_notify import format_clock, format_digest, format_step_nudge

log = logging.getLogger(__name__)

API = "https://api.telegram.org"
LINK_MINUTES = 20
DIGEST_HOUR = 10
QUIET_START = 21
QUIET_END = 9
STEP_LEAD = timedelta(hours=2)
MAX_SEND_PER_TICK = 40


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.google_calendar_timezone or "Europe/Moscow")


def _local(now: datetime | None = None) -> datetime:
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(_tz())


def local_date(now: datetime | None = None) -> str:
    return _local(now).date().isoformat()


def in_quiet_hours(now: datetime | None = None) -> bool:
    hour = _local(now).hour
    return hour >= QUIET_START or hour < QUIET_END


def digest_window(now: datetime | None = None) -> bool:
    return _local(now).hour >= DIGEST_HOUR


async def get_state(session: AsyncSession) -> TelegramBotState:
    row = await session.get(TelegramBotState, 1)
    if row is None:
        row = TelegramBotState(id=1, update_offset=0)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


def bot_token(state: TelegramBotState) -> str:
    return (unseal(state.bot_token) or settings.telegram_bot_token or "").strip()


def bot_configured(state: TelegramBotState) -> bool:
    return bool(bot_token(state))


async def hydrate_bot_username(session: AsyncSession, state: TelegramBotState) -> TelegramBotState:
    token = bot_token(state)
    if not token or (state.bot_username or "").strip():
        return state
    me = await fetch_me(token)
    username = str(me.get("username") or "").strip()
    if username:
        state.bot_username = username
        await session.commit()
        await session.refresh(state)
    return state


async def save_bot_token(session: AsyncSession, token: str) -> TelegramBotState:
    state = await get_state(session)
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Нужен токен бота")
    me = await fetch_me(cleaned)
    username = str(me.get("username") or "").strip()
    if not me.get("id") or not username:
        raise ValueError("Telegram не принял токен. Проверь, что это токен от @BotFather.")
    state.bot_token = seal(cleaned)
    state.bot_username = username
    await session.commit()
    await session.refresh(state)
    return state


async def fetch_me(token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{API}/bot{token}/getMe")
    if response.status_code >= 400:
        return {}
    data = response.json()
    if not data.get("ok"):
        return {}
    result = data.get("result") or {}
    return result if isinstance(result, dict) else {}


async def send_text(token: str, chat_id: int, text: str) -> bool:
    body = text.strip()
    if not body or not chat_id:
        return False
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": body[:4000], "disable_web_page_preview": True},
        )
    if response.status_code >= 400:
        log.warning("telegram bot send failed chat=%s status=%s", chat_id, response.status_code)
        return False
    data = response.json()
    return bool(data.get("ok"))


async def ensure_bind(session: AsyncSession, user_id: int) -> TelegramBotBind:
    row = (
        await session.execute(select(TelegramBotBind).where(TelegramBotBind.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        row = TelegramBotBind(user_id=user_id, open_internship_slugs=[])
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def open_internship_slug_set(session: AsyncSession) -> set[str]:
    monitors = {
        row.program_slug: row
        for row in (await session.execute(select(InternshipMonitor))).scalars().all()
    }
    out: set[str] = set()
    for program in programs():
        monitor = monitors.get(program.slug)
        status = (monitor.live_status if monitor else program.catalog_status) or ""
        if status == "open":
            out.add(program.slug)
    return out


async def issue_link(session: AsyncSession, user: User) -> dict:
    state = await hydrate_bot_username(session, await get_state(session))
    token_value = bot_token(state)
    if not token_value:
        raise RuntimeError("unavailable")
    username = (state.bot_username or "").strip()
    if not username:
        raise RuntimeError("unavailable")
    old = (
        await session.execute(select(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id))
    ).scalars().all()
    for row in old:
        await session.delete(row)
    code = secrets.token_urlsafe(18)
    session.add(
        TelegramLinkToken(
            token=code,
            user_id=user.id,
            expires_at=_now() + timedelta(minutes=LINK_MINUTES),
        )
    )
    await session.commit()
    return {"url": f"https://t.me/{username}?start={code}", "username": username}


def bind_status(state: TelegramBotState, row: TelegramBotBind | None) -> dict:
    connected = bool(row and row.telegram_user_id and row.chat_id)
    return {
        "available": bot_configured(state),
        "username": state.bot_username,
        "connected": connected,
        "paused": bool(row.paused) if row else False,
        "telegram_username": row.username if row else None,
        "want_vacancies": bool(row.want_vacancies) if row else True,
        "want_internships": bool(row.want_internships) if row else True,
        "want_hackathons": bool(row.want_hackathons) if row else True,
        "want_steps": bool(row.want_steps) if row else True,
        "want_ping": bool(row.want_ping) if row else True,
    }


async def apply_prefs(row: TelegramBotBind, payload: dict) -> None:
    for key in ("want_vacancies", "want_internships", "want_hackathons", "want_steps", "want_ping"):
        if key in payload and payload[key] is not None:
            setattr(row, key, bool(payload[key]))


async def unlink(session: AsyncSession, row: TelegramBotBind) -> None:
    row.telegram_user_id = None
    row.chat_id = None
    row.username = None
    row.paused = False
    await session.commit()


async def noticed(session: AsyncSession, user_id: int, kind: str, subject_key: str) -> bool:
    found = (
        await session.execute(
            select(TelegramNotice.id).where(
                TelegramNotice.user_id == user_id,
                TelegramNotice.kind == kind,
                TelegramNotice.subject_key == subject_key,
            )
        )
    ).scalar_one_or_none()
    return found is not None


async def collect_vacancies(session: AsyncSession, bind: TelegramBotBind) -> list[Vacancy]:
    if not bind.want_vacancies or not bind.cursor_at:
        return []
    rows = (
        await session.execute(
            select(Vacancy)
            .where(
                Vacancy.user_id == bind.user_id,
                Vacancy.duplicate_of_id.is_(None),
                Vacancy.pipeline_stage == PipelineStage.INBOX,
                Vacancy.created_at > bind.cursor_at,
            )
            .order_by(Vacancy.id.desc())
            .limit(40)
        )
    ).scalars().all()
    return list(rows)


async def collect_internships(session: AsyncSession, bind: TelegramBotBind) -> tuple[list[str], set[str]]:
    current = await open_internship_slug_set(session)
    if not bind.want_internships:
        return [], current
    seen = {str(item) for item in (bind.open_internship_slugs or [])}
    names = []
    by_slug = {program.slug: program.name for program in programs()}
    for slug in sorted(current - seen):
        names.append(by_slug.get(slug, slug))
    return names, current


async def collect_hackathons(session: AsyncSession, bind: TelegramBotBind) -> list[tuple[str, str | None]]:
    if not bind.want_hackathons or not bind.cursor_at:
        return []
    rows = (
        await session.execute(
            select(HackathonEvent).where(HackathonEvent.first_seen_at > bind.cursor_at)
        )
    ).scalars().all()
    out: list[tuple[str, str | None]] = []
    for row in rows:
        if not compute_is_new(
            event_status=row.event_status,
            registration_status=row.registration_status,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
        ):
            continue
        out.append((row.title, row.url))
    return out[:20]


def ping_subject(row: Vacancy) -> str:
    start = row.pinged_at or row.outreach_at or row.last_touch_at
    stamp = start.isoformat() if start else "x"
    return f"{row.id}:{stamp}"


async def collect_pings(session: AsyncSession, bind: TelegramBotBind) -> list[tuple[Vacancy, int | None]]:
    if not bind.want_ping:
        return []
    rows = (
        await session.execute(
            select(Vacancy).where(
                Vacancy.user_id == bind.user_id,
                Vacancy.duplicate_of_id.is_(None),
                Vacancy.pipeline_stage == PipelineStage.WAITING,
            )
        )
    ).scalars().all()
    now = _now()
    due: list[tuple[Vacancy, int | None]] = []
    for row in rows:
        if not ping_due(row, now):
            continue
        if await noticed(session, bind.user_id, "ping", ping_subject(row)):
            continue
        due.append((row, silence_days(row, now)))
    due.sort(key=lambda item: item[1] or 0, reverse=True)
    return due


async def collect_today_steps(
    session: AsyncSession, bind: TelegramBotBind
) -> list[tuple[VacancyEvent, Vacancy, str]]:
    if not bind.want_steps:
        return []
    local = _local()
    start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC).replace(tzinfo=None)
    end = start + timedelta(days=1)
    now = _now()
    rows = (
        await session.execute(
            select(VacancyEvent, Vacancy)
            .join(Vacancy, Vacancy.id == VacancyEvent.vacancy_id)
            .where(
                VacancyEvent.user_id == bind.user_id,
                VacancyEvent.starts_at >= max(start, now),
                VacancyEvent.starts_at < end,
            )
            .order_by(VacancyEvent.starts_at)
        )
    ).all()
    out: list[tuple[VacancyEvent, Vacancy, str]] = []
    for event, vacancy in rows:
        if await noticed(session, bind.user_id, "step", str(event.id)):
            continue
        out.append((event, vacancy, format_clock(event.starts_at)))
    return out


async def collect_soon_steps(
    session: AsyncSession, bind: TelegramBotBind
) -> list[tuple[VacancyEvent, Vacancy, str]]:
    if not bind.want_steps:
        return []
    now = _now()
    until = now + STEP_LEAD
    rows = (
        await session.execute(
            select(VacancyEvent, Vacancy)
            .join(Vacancy, Vacancy.id == VacancyEvent.vacancy_id)
            .where(
                VacancyEvent.user_id == bind.user_id,
                VacancyEvent.starts_at > now,
                VacancyEvent.starts_at <= until,
            )
            .order_by(VacancyEvent.starts_at)
        )
    ).all()
    out: list[tuple[VacancyEvent, Vacancy, str]] = []
    for event, vacancy in rows:
        if await noticed(session, bind.user_id, "step", str(event.id)):
            continue
        out.append((event, vacancy, format_clock(event.starts_at)))
    return out


def remember(session: AsyncSession, user_id: int, kind: str, subject_key: str) -> None:
    session.add(TelegramNotice(user_id=user_id, kind=kind, subject_key=subject_key, sent_at=_now()))


async def build_digest(
    session: AsyncSession, bind: TelegramBotBind
) -> tuple[str | None, set[str], list[tuple[Vacancy, int | None]], list[tuple[VacancyEvent, Vacancy, str]]]:
    vacancies = await collect_vacancies(session, bind)
    internships, open_slugs = await collect_internships(session, bind)
    hackathons = await collect_hackathons(session, bind)
    pings = await collect_pings(session, bind)
    steps = await collect_today_steps(session, bind)
    text = format_digest(
        vacancies=vacancies,
        internships=internships,
        hackathons=hackathons,
        pings=pings,
        steps=steps,
        origin=public_origin(),
    )
    return text, open_slugs, pings, steps


async def send_for_bind(token: str, bind: TelegramBotBind, text: str | None) -> bool:
    if not text or not bind.chat_id:
        return False
    return await send_text(token, bind.chat_id, text)


async def run_digest_for(session: AsyncSession, token: str, bind: TelegramBotBind) -> bool:
    today = local_date()
    if bind.last_digest_on == today:
        return False
    if not digest_window() or in_quiet_hours():
        return False
    text, open_slugs, pings, steps = await build_digest(session, bind)
    if not text:
        bind.last_digest_on = today
        bind.cursor_at = _now()
        bind.open_internship_slugs = sorted(open_slugs)
        flag_modified(bind, "open_internship_slugs")
        await session.commit()
        return False
    if await noticed(session, bind.user_id, "digest", today):
        return False
    ok = await send_for_bind(token, bind, text)
    if ok:
        remember(session, bind.user_id, "digest", today)
        for row, _days in pings:
            remember(session, bind.user_id, "ping", ping_subject(row))
        for event, _vacancy, _when in steps:
            remember(session, bind.user_id, "step", str(event.id))
        bind.last_digest_on = today
        bind.cursor_at = _now()
        bind.open_internship_slugs = sorted(open_slugs)
        flag_modified(bind, "open_internship_slugs")
        await session.commit()
    else:
        await session.rollback()
    return ok


async def run_step_nudge_for(session: AsyncSession, token: str, bind: TelegramBotBind) -> bool:
    items = await collect_soon_steps(session, bind)
    text = format_step_nudge(items)
    if not text:
        return False
    ok = await send_for_bind(token, bind, text)
    if ok:
        for event, _vacancy, _when in items:
            remember(session, bind.user_id, "step", str(event.id))
        await session.commit()
    else:
        await session.rollback()
    return ok


async def tick(session: AsyncSession) -> dict:
    state = await get_state(session)
    token = bot_token(state)
    if not token:
        return {"sent": 0}
    binds = (
        await session.execute(
            select(TelegramBotBind).where(
                TelegramBotBind.telegram_user_id.isnot(None),
                TelegramBotBind.chat_id.isnot(None),
                TelegramBotBind.paused.is_(False),
            )
        )
    ).scalars().all()
    sent = 0
    for bind in binds:
        if sent >= MAX_SEND_PER_TICK:
            break
        try:
            if await run_digest_for(session, token, bind):
                sent += 1
                continue
            if await run_step_nudge_for(session, token, bind):
                sent += 1
        except Exception:
            log.exception("telegram bot tick user=%s", bind.user_id)
            await session.rollback()
    return {"sent": sent}


async def _bind_from_start(session: AsyncSession, code: str, telegram_user_id: int, chat_id: int, username: str | None) -> str:
    token_row = await session.get(TelegramLinkToken, code)
    if token_row is None or token_row.expires_at < _now():
        return "Ссылка устарела. Открой HuntOS → Уведомления ещё раз."
    taken = (
        await session.execute(
            select(TelegramBotBind).where(TelegramBotBind.telegram_user_id == telegram_user_id)
        )
    ).scalar_one_or_none()
    if taken is not None and taken.user_id != token_row.user_id:
        return "Этот Telegram уже привязан к другому аккаунту."
    bind = await ensure_bind(session, token_row.user_id)
    bind.telegram_user_id = telegram_user_id
    bind.chat_id = chat_id
    bind.username = (username or "").lstrip("@") or None
    bind.paused = False
    bind.cursor_at = _now()
    bind.open_internship_slugs = sorted(await open_internship_slug_set(session))
    flag_modified(bind, "open_internship_slugs")
    await session.delete(token_row)
    await session.commit()
    return "Готово. Письма только про твои вакансии, без лишнего шума. /stop — пауза."


async def handle_message(session: AsyncSession, payload: dict) -> str | None:
    text = str(payload.get("text") or "").strip()
    chat = payload.get("chat") or {}
    sender = payload.get("from") or {}
    chat_id = chat.get("id")
    telegram_user_id = sender.get("id")
    if not text or chat_id is None or telegram_user_id is None:
        return None
    username = sender.get("username")
    low = text.split()[0].split("@", 1)[0].lower()
    bind = (
        await session.execute(
            select(TelegramBotBind).where(TelegramBotBind.telegram_user_id == int(telegram_user_id))
        )
    ).scalar_one_or_none()

    if low == "/start":
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        if code:
            return await _bind_from_start(session, code, int(telegram_user_id), int(chat_id), username)
        if bind and bind.chat_id:
            return "Уже связано. Настройки — в HuntOS → Уведомления."
        return "Открой HuntOS → Уведомления и нажми «Подключить»."
    if bind is None:
        return "Сначала свяжи аккаунт в HuntOS → Уведомления."
    if low == "/stop":
        bind.paused = True
        await session.commit()
        return "Пауза. /go — снова включить."
    if low in {"/go", "/start"}:
        bind.paused = False
        bind.chat_id = int(chat_id)
        await session.commit()
        return "Снова пишу, только когда есть повод."
    if low == "/help":
        return "Раз в сутки — новые вакансии, стажировки, хакатоны, пинг HR. Перед собесом — коротко. /stop — пауза."
    return None


async def poll_updates(session: AsyncSession) -> int:
    state = await get_state(session)
    token = bot_token(state)
    if not token:
        return 0
    params = {"timeout": 0, "offset": int(state.update_offset or 0) + 1}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{API}/bot{token}/getUpdates", params=params)
    if response.status_code >= 400:
        return 0
    data = response.json()
    if not data.get("ok"):
        return 0
    updates = data.get("result") or []
    handled = 0
    last_id = state.update_offset or 0
    for update in updates:
        last_id = max(last_id, int(update.get("update_id") or 0))
        message = update.get("message") or update.get("edited_message") or {}
        reply = await handle_message(session, message)
        chat_id = (message.get("chat") or {}).get("id")
        if reply and chat_id:
            await send_text(token, int(chat_id), reply)
            handled += 1
    if last_id != (state.update_offset or 0):
        state.update_offset = last_id
        await session.commit()
    return handled
