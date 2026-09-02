from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from app.config import settings
from app.models.host_telegram import HostTelegram


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def get_host_row(session: AsyncSession) -> HostTelegram:
    row = await session.get(HostTelegram, 1)
    if row is None:
        row = HostTelegram(id=1, status="disconnected")
        session.add(row)
        await session.flush()
    return row


def _credentials(row: HostTelegram) -> tuple[int, str]:
    api_id = row.api_id or settings.telegram_api_id
    api_hash = (row.api_hash or settings.telegram_api_hash or "").strip()
    if not api_id or not api_hash:
        raise HTTPException(
            400,
            "Нужны api_id и api_hash с my.telegram.org — вставь в форму или в .env "
            "(TELEGRAM_API_ID / TELEGRAM_API_HASH)",
        )
    return int(api_id), api_hash


def host_status_dict(row: HostTelegram) -> dict[str, Any]:
    return {
        "connected": row.status == "connected" and bool(row.session_string),
        "status": row.status,
        "phone": row.phone,
        "username": row.username,
        "display_name": row.display_name,
        "error": row.error,
        "connected_at": row.connected_at.isoformat() if row.connected_at else None,
        "api_id_set": bool(row.api_id or settings.telegram_api_id),
        "waiting_code": row.status == "waiting_code",
        "needs_password": row.status == "needs_password",
    }


def _client(api_id: int, api_hash: str, session_string: str | None = None) -> TelegramClient:
    return TelegramClient(StringSession(session_string or ""), api_id, api_hash)


async def start_login(
    session: AsyncSession,
    *,
    phone: str,
    api_id: int | None,
    api_hash: str | None,
) -> HostTelegram:
    row = await get_host_row(session)
    cleaned = phone.strip().replace(" ", "")
    if not cleaned.startswith("+"):
        raise HTTPException(400, "Телефон в международном формате, например +79001234567")
    if api_id:
        row.api_id = int(api_id)
    if api_hash and api_hash.strip():
        row.api_hash = api_hash.strip()
    creds = _credentials(row)
    client = _client(*creds)
    try:
        await client.connect()
        sent = await client.send_code_request(cleaned)
        row.phone = cleaned
        row.phone_code_hash = sent.phone_code_hash
        row.session_string = client.session.save()
        row.status = "waiting_code"
        row.error = None
        await session.commit()
        await session.refresh(row)
        return row
    except FloodWaitError as exc:
        row.status = "error"
        row.error = f"Telegram просит подождать {exc.seconds} сек"
        await session.commit()
        raise HTTPException(429, row.error) from exc
    except Exception as exc:
        row.status = "error"
        row.error = str(exc)[:500]
        await session.commit()
        raise HTTPException(400, row.error) from exc
    finally:
        await client.disconnect()


async def confirm_login(
    session: AsyncSession,
    *,
    code: str,
    password: str | None,
) -> HostTelegram:
    row = await get_host_row(session)
    if not row.session_string or not row.phone:
        raise HTTPException(400, "Сначала запроси код")
    creds = _credentials(row)
    client = _client(*creds, row.session_string)
    try:
        await client.connect()
        try:
            if row.status == "needs_password" or (password and not code.strip()):
                if not password:
                    raise HTTPException(400, "Нужен облачный пароль 2FA")
                await client.sign_in(password=password)
            else:
                await client.sign_in(
                    row.phone,
                    code.strip(),
                    phone_code_hash=row.phone_code_hash or "",
                )
        except SessionPasswordNeededError:
            row.status = "needs_password"
            row.session_string = client.session.save()
            row.error = None
            await session.commit()
            await session.refresh(row)
            return row
        me = await client.get_me()
        row.session_string = client.session.save()
        row.phone_code_hash = None
        row.status = "connected"
        row.error = None
        row.username = getattr(me, "username", None)
        names = [getattr(me, "first_name", None), getattr(me, "last_name", None)]
        row.display_name = " ".join(p for p in names if p) or row.username
        row.connected_at = _now()
        await session.commit()
        await session.refresh(row)
        return row
    except PhoneCodeInvalidError as exc:
        raise HTTPException(400, "Неверный код") from exc
    except PhoneCodeExpiredError as exc:
        row.status = "disconnected"
        row.error = "Код истёк — запроси новый"
        await session.commit()
        raise HTTPException(400, row.error) from exc
    except HTTPException:
        raise
    except Exception as exc:
        row.status = "error"
        row.error = str(exc)[:500]
        await session.commit()
        raise HTTPException(400, row.error) from exc
    finally:
        await client.disconnect()


async def disconnect_host(session: AsyncSession) -> HostTelegram:
    row = await get_host_row(session)
    if row.session_string:
        try:
            creds = _credentials(row)
            client = _client(*creds, row.session_string)
            await client.connect()
            await client.log_out()
            await client.disconnect()
        except Exception:
            pass
    row.session_string = None
    row.phone_code_hash = None
    row.status = "disconnected"
    row.error = None
    row.username = None
    row.display_name = None
    row.connected_at = None
    await session.commit()
    await session.refresh(row)
    return row


async def connected_client(session: AsyncSession) -> TelegramClient:
    row = await get_host_row(session)
    if row.status != "connected" or not row.session_string:
        raise HTTPException(400, "Хост ещё не подключил Telegram")
    creds = _credentials(row)
    client = _client(*creds, row.session_string)
    await client.connect()
    if not await client.is_user_authorized():
        row.status = "disconnected"
        row.error = "Сессия Telegram истекла — подключи заново"
        await session.commit()
        await client.disconnect()
        raise HTTPException(400, row.error)
    return client
