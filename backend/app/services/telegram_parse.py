from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FloodWaitError, InviteHashExpiredError, UserAlreadyParticipantError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import Channel, Chat

from app.config import settings
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_parse_run import TelegramParseRun
from app.models.telegram_post import TelegramPost
from app.models.user import User
from app.models.user_profile import UserProfile
from app.prompts.telegram_vacancy import EXTRACT_SYSTEM, EXTRACT_USER
from app.services.scraper.engine import upsert_vacancy
from app.services.scraper.salary import parse_salary
from app.services.scoring.llm import complete, config_from_profile, extract_json
from app.services.telegram_host import connected_client, get_host_row

log = logging.getLogger(__name__)

_JOBISH = re.compile(
    r"(ваканси|ищем|ищет|required|зарплат|оклад|salary|удалён|удален|hybrid|офис|"
    r"python|developer|разработ|engineer|backend|frontend|fullstack|devops|qa |"
    r"product manager|аналитик|designer|дизайнер|middle|senior|junior|lead\b)",
    re.IGNORECASE,
)
_AT = re.compile(r"(?<!\w)@([a-zA-Z][a-zA-Z0-9_]{3,31})")
_GRADES = ("intern", "junior", "middle", "senior", "lead", "head")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def fail_open_telegram_runs(session: AsyncSession, *, reason: str) -> int:
    rows = (
        await session.execute(select(TelegramParseRun).where(TelegramParseRun.status == "running"))
    ).scalars().all()
    now = _now()
    for run in rows:
        run.status = "error"
        run.error = reason
        run.finished_at = now
    if rows:
        await session.commit()
    return len(rows)


def _heuristic(text: str, channel: str) -> dict | None:
    body = (text or "").strip()
    if len(body) < 80 or not _JOBISH.search(body):
        return None
    first = next((line.strip() for line in body.splitlines() if line.strip()), "Вакансия")
    title = re.sub(r"^[#\-\d\.\)\s]+", "", first)[:180] or "Вакансия"
    alias = None
    for match in _AT.finditer(body):
        handle = match.group(1).lower()
        if handle != channel.lower():
            alias = handle
            break
    grade = next((g for g in _GRADES if re.search(rf"\b{g}\b", body, re.I)), None)
    fmt = None
    low = body.lower()
    if "удал" in low or "remote" in low:
        fmt = "удалённо"
    elif "гибрид" in low or "hybrid" in low:
        fmt = "гибрид"
    elif "офис" in low:
        fmt = "офис"
    salary_line = next((ln for ln in body.splitlines() if re.search(r"(зп|зарплат|salary|₽|руб|\$)", ln, re.I)), None)
    return {
        "title": title[:512],
        "company": None,
        "grade": grade,
        "work_format": fmt,
        "location": None,
        "salary_raw": salary_line.strip()[:128] if salary_line else None,
        "telegram_alias": alias,
        "skills": [],
        "requirements": body[:8000],
        "description": body[:8000],
    }


async def _extract(session: AsyncSession, *, text: str, channel: str, date: str) -> dict | None:
    host = (
        await session.execute(select(User).where(User.is_host.is_(True)).order_by(User.id).limit(1))
    ).scalar_one_or_none()
    profile = None
    if host:
        profile = (
            await session.execute(select(UserProfile).where(UserProfile.user_id == host.id))
        ).scalar_one_or_none()
    cfg = config_from_profile(profile)
    try:
        raw = await complete(
            cfg,
            system=EXTRACT_SYSTEM,
            user=EXTRACT_USER.format(channel=channel, date=date, text=text[:8000]),
            json_mode=True,
        )
        data = extract_json(raw)
        if not data.get("is_vacancy"):
            return None
        return data
    except Exception as exc:
        log.info("telegram extract fallback: %s", exc)
        return _heuristic(text, channel)


def _payload_from_extract(
    data: dict,
    *,
    source_id: str,
    source_url: str | None,
    published_at: datetime | None,
    channel_username: str,
) -> dict:
    salary_raw = data.get("salary_raw")
    lo, hi, cur = parse_salary(salary_raw)
    alias = (data.get("telegram_alias") or "").lstrip("@").strip() or None
    title = (data.get("title") or "Вакансия").strip()[:512]
    skills = data.get("skills") if isinstance(data.get("skills"), list) else []
    return {
        "source": "telegram",
        "source_id": source_id,
        "source_url": source_url,
        "title": title,
        "company": (data.get("company") or None),
        "grade": data.get("grade") if data.get("grade") in _GRADES else None,
        "work_format": data.get("work_format") or None,
        "location": data.get("location") or None,
        "salary_raw": salary_raw,
        "salary_min": lo,
        "salary_max": hi,
        "salary_currency": cur,
        "description": data.get("description") or None,
        "requirements": data.get("requirements") or None,
        "skills": [str(s) for s in skills if s][:24],
        "tags": [f"tg:{channel_username}"],
        "telegram_alias": alias,
        "published_at": published_at,
    }


async def recipient_ids(session: AsyncSession) -> list[int]:
    return list((await session.execute(select(User.id).order_by(User.id))).scalars().all())


async def fanout_post(session: AsyncSession, post: TelegramPost, user_ids: list[int] | None = None) -> tuple[int, int]:
    payload = dict(post.payload or {})
    payload["source"] = "telegram"
    payload["source_id"] = f"{post.channel_id}:{post.message_id}"
    payload["source_url"] = post.source_url
    if post.published_at:
        payload["published_at"] = post.published_at
    ids = user_ids if user_ids is not None else await recipient_ids(session)
    new_count = 0
    updated = 0
    for uid in ids:
        _, kind = await upsert_vacancy(session, payload, scraper_config_id=None, user_id=uid)
        if kind == "new":
            new_count += 1
        else:
            updated += 1
    return new_count, updated


async def backfill_user_telegram(session: AsyncSession, user_id: int, *, days: int = 14) -> int:
    since = _now() - timedelta(days=days)
    posts = (
        await session.execute(
            select(TelegramPost)
            .where(TelegramPost.published_at.is_(None) | (TelegramPost.published_at >= since))
            .order_by(TelegramPost.id.desc())
            .limit(80)
        )
    ).scalars().all()
    created = 0
    for post in posts:
        new, _updated = await fanout_post(session, post, user_ids=[user_id])
        created += new
    await session.commit()
    return created


async def ensure_user_telegram_pool(session: AsyncSession, user_id: int) -> int:
    from app.models.vacancy import Vacancy

    has = (
        await session.execute(
            select(Vacancy.id).where(Vacancy.user_id == user_id, Vacancy.source == "telegram").limit(1)
        )
    ).first()
    if has is not None:
        return 0
    return await backfill_user_telegram(session, user_id)


async def _resolve_entity(client, channel: TelegramChannel):
    if channel.telegram_id:
        try:
            return await client.get_entity(channel.telegram_id)
        except Exception:
            pass
    if channel.invite_hash:
        try:
            result = await client(ImportChatInviteRequest(channel.invite_hash))
            chats = getattr(result, "chats", None) or []
            if chats:
                return chats[0]
        except UserAlreadyParticipantError:
            if channel.telegram_id:
                return await client.get_entity(channel.telegram_id)
        except InviteHashExpiredError as exc:
            raise RuntimeError("Инвайт истёк") from exc
    entity = await client.get_entity(channel.username)
    try:
        from telethon.tl.functions.channels import JoinChannelRequest

        await client(JoinChannelRequest(entity))
    except UserAlreadyParticipantError:
        pass
    except Exception as exc:
        log.info("join %s: %s", channel.username, exc)
    return entity


async def _parse_channel(session: AsyncSession, client, channel: TelegramChannel) -> tuple[int, int]:
    found = 0
    new_posts = 0
    entity = await _resolve_entity(client, channel)
    if isinstance(entity, (Channel, Chat)):
        channel.title = getattr(entity, "title", channel.title)
        channel.telegram_id = getattr(entity, "id", channel.telegram_id)
        uname = getattr(entity, "username", None)
        if uname and not channel.invite_hash:
            channel.username = uname.lower()
    channel.joined = True
    limit = settings.telegram_messages_per_channel
    messages = []
    async for message in client.iter_messages(entity, limit=limit):
        messages.append(message)
        if channel.last_message_id and message.id <= channel.last_message_id:
            break
    messages.reverse()
    username = channel.username.lstrip("+")
    for message in messages:
        text = (message.message or message.raw_text or "").strip()
        if not text or getattr(message, "action", None):
            continue
        found += 1
        existing = (
            await session.execute(
                select(TelegramPost).where(
                    TelegramPost.channel_id == channel.id,
                    TelegramPost.message_id == message.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        published = message.date.replace(tzinfo=None) if message.date else _now()
        if message.date and message.date.tzinfo:
            published = message.date.astimezone(UTC).replace(tzinfo=None)
        extracted = await _extract(
            session,
            text=text,
            channel=username,
            date=str(published),
        )
        if not extracted:
            continue
        if channel.invite_hash:
            source_url = f"https://t.me/{channel.username}"
        else:
            source_url = f"https://t.me/{channel.username}/{message.id}"
        source_id = f"{channel.id}:{message.id}"
        payload = _payload_from_extract(
            extracted,
            source_id=source_id,
            source_url=source_url,
            published_at=published,
            channel_username=channel.username,
        )
        post = TelegramPost(
            channel_id=channel.id,
            message_id=message.id,
            source_url=source_url,
            payload={k: v for k, v in payload.items() if k != "published_at"},
            published_at=published,
            raw_text=text[:20000],
        )
        session.add(post)
        await session.flush()
        await fanout_post(session, post)
        new_posts += 1
        await session.commit()
        await asyncio.sleep(0.4)
    if messages:
        channel.last_message_id = max(m.id for m in messages)
    channel.last_parsed_at = _now()
    channel.status = "active"
    channel.error = None
    await session.commit()
    return found, new_posts


async def parse_all_channels(session: AsyncSession) -> TelegramParseRun:
    running = (
        await session.execute(select(TelegramParseRun).where(TelegramParseRun.status == "running"))
    ).scalar_one_or_none()
    if running:
        return running
    run = TelegramParseRun(started_at=_now(), status="running")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    run_id = run.id
    found = 0
    new_count = 0
    error: str | None = None
    status = "ok"
    client = None
    try:
        host = await get_host_row(session)
        if host.status != "connected":
            raise RuntimeError("Хост ещё не подключил Telegram")
        client = await connected_client(session)
        channels = (
            await session.execute(
                select(TelegramChannel).where(TelegramChannel.enabled.is_(True)).order_by(TelegramChannel.id)
            )
        ).scalars().all()
        for channel in channels:
            try:
                c_found, c_new = await _parse_channel(session, client, channel)
                found += c_found
                new_count += c_new
                await asyncio.sleep(1.2)
            except FloodWaitError as exc:
                channel.status = "error"
                channel.error = f"лимит Telegram, ждать {exc.seconds} сек"
                await session.commit()
                error = channel.error
                status = "error"
                break
            except Exception as exc:
                log.exception("telegram channel %s", channel.username)
                channel.status = "error"
                channel.error = str(exc)[:500]
                await session.commit()
    except Exception as exc:
        log.exception("telegram parse")
        status = "error"
        error = str(exc)[:2000]
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
    run = await session.get(TelegramParseRun, run_id)
    if run is None:
        run = TelegramParseRun(started_at=_now())
        session.add(run)
    run.status = status
    run.error = error
    run.found_count = found
    run.new_count = new_count
    run.finished_at = _now()
    await session.commit()
    return run
