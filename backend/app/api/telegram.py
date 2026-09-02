from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_parse_run import TelegramParseRun
from app.models.user import User
from app.services.deps import get_current_user, require_host
from app.services.scoring.scorer import score_pending
from app.services.telegram import parse_channel_url
from app.services.telegram_host import (
    confirm_login,
    disconnect_host,
    get_host_row,
    host_status_dict,
    start_login,
)
from app.services.telegram_parse import backfill_user_telegram, parse_all_channels, recipient_ids

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class HostStartIn(BaseModel):
    phone: str
    api_id: int | None = None
    api_hash: str | None = None


class HostConfirmIn(BaseModel):
    code: str = ""
    password: str | None = None


class ChannelIn(BaseModel):
    url: str


class ChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    title: str | None
    enabled: bool
    joined: bool
    status: str
    error: str | None
    last_parsed_at: datetime | None
    added_url: str | None
    added_by_user_id: int | None


class ParseRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    found_count: int
    new_count: int
    error: str | None


class PoolOut(BaseModel):
    host: dict
    channels: list[ChannelOut]
    last_run: ParseRunOut | None


@router.get("/pool", response_model=PoolOut)
async def telegram_pool(
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> PoolOut:
    host = await get_host_row(session)
    channels = (
        await session.execute(select(TelegramChannel).order_by(TelegramChannel.id.desc()))
    ).scalars().all()
    last = (
        await session.execute(select(TelegramParseRun).order_by(TelegramParseRun.id.desc()).limit(1))
    ).scalar_one_or_none()
    data = host_status_dict(host)
    return PoolOut(
        host=data,
        channels=[ChannelOut.model_validate(row) for row in channels],
        last_run=ParseRunOut.model_validate(last) if last else None,
    )


@router.post("/host/start")
async def host_start(
    payload: HostStartIn,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> dict:
    row = await start_login(
        session,
        phone=payload.phone,
        api_id=payload.api_id,
        api_hash=payload.api_hash,
    )
    return host_status_dict(row)


@router.post("/host/confirm")
async def host_confirm(
    payload: HostConfirmIn,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> dict:
    row = await confirm_login(session, code=payload.code, password=payload.password)
    return host_status_dict(row)


@router.post("/host/disconnect")
async def host_disconnect(
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> dict:
    row = await disconnect_host(session)
    return host_status_dict(row)


@router.post("/channels", response_model=ChannelOut)
async def add_channel(
    payload: ChannelIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> ChannelOut:
    try:
        ref = parse_channel_url(payload.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    existing = (
        await session.execute(select(TelegramChannel).where(TelegramChannel.username == ref.username))
    ).scalar_one_or_none()
    if existing:
        return ChannelOut.model_validate(existing)
    row = TelegramChannel(
        added_by_user_id=user.id,
        username=ref.username,
        invite_hash=ref.invite_hash,
        added_url=ref.added_url[:512],
        status="queued",
        enabled=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ChannelOut.model_validate(row)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> dict:
    row = await session.get(TelegramChannel, channel_id)
    if row is None:
        raise HTTPException(404, "Канал не найден")
    await session.delete(row)
    await session.commit()
    return {"ok": True}


@router.post("/join")
async def join_pool(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    created = await backfill_user_telegram(session, user.id)
    return {"ok": True, "new_count": created}


async def _parse_and_score() -> None:
    async with SessionLocal() as session:
        try:
            await parse_all_channels(session)
        except Exception:
            return
        for uid in await recipient_ids(session):
            try:
                await score_pending(session, user_id=uid, limit=10)
            except Exception:
                await session.rollback()


@router.post("/parse")
async def parse_now(
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _host: User = Depends(require_host),
) -> dict:
    host = await get_host_row(session)
    if host.status != "connected":
        raise HTTPException(400, "Хост ещё не подключил Telegram")
    running = (
        await session.execute(select(TelegramParseRun).where(TelegramParseRun.status == "running"))
    ).scalar_one_or_none()
    if running:
        return {"ok": True, "status": "running"}
    background.add_task(_parse_and_score)
    return {"ok": True, "status": "started"}
