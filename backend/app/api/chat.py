from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.chat import ChatMessage, Conversation
from app.models.user import User
from app.services.chat import (
    get_or_create_dm,
    host_user,
    is_online,
    last_message,
    member_row,
    now_utc,
    peer_name,
    require_member,
    touch_presence,
    unread_stmt,
)
from app.services.deps import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


class PresenceOut(BaseModel):
    online: bool
    last_seen_at: datetime | None = None
    name: str


class ThreadOut(BaseModel):
    id: int
    peer_id: int
    peer_name: str
    online: bool
    last_seen_at: datetime | None = None
    last_body: str | None = None
    last_at: datetime | None = None
    unread: int = 0


class InboxOut(BaseModel):
    host: bool
    unread_total: int
    admin: PresenceOut
    threads: list[ThreadOut]


class MessageOut(BaseModel):
    id: int
    sender_id: int
    mine: bool
    body: str
    created_at: datetime


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class OpenIn(BaseModel):
    user_id: int | None = None


def _presence(user: User, *, name: str) -> PresenceOut:
    return PresenceOut(online=is_online(user.last_seen_at), last_seen_at=user.last_seen_at, name=name)


def _preview(body: str | None) -> str | None:
    if not body:
        return None
    text = " ".join(body.split())
    return text if len(text) <= 80 else f"{text[:79].rstrip()}…"


async def _thread_out(session: AsyncSession, viewer: User, conv: Conversation, peer: User) -> ThreadOut:
    mine = await member_row(session, conv.id, viewer.id)
    unread = 0
    if mine is not None:
        unread = int((await session.execute(unread_stmt(viewer.id, conv.id, mine.last_read_at))).scalar_one())
    msg = await last_message(session, conv.id)
    return ThreadOut(
        id=conv.id,
        peer_id=peer.id,
        peer_name=peer_name(viewer, peer),
        online=is_online(peer.last_seen_at),
        last_seen_at=peer.last_seen_at,
        last_body=_preview(msg.body if msg else None),
        last_at=msg.created_at if msg else conv.last_message_at,
        unread=unread,
    )


@router.get("/inbox", response_model=InboxOut)
async def chat_inbox(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> InboxOut:
    await touch_presence(session, user)
    admin = await host_user(session)
    if user.is_host:
        people = (
            await session.execute(select(User).where(User.id != user.id).order_by(User.email))
        ).scalars().all()
        threads: list[ThreadOut] = []
        for peer in people:
            conv = await get_or_create_dm(session, user, peer)
            threads.append(await _thread_out(session, user, conv, peer))
        threads.sort(key=lambda row: (row.last_at is None, -(row.last_at.timestamp() if row.last_at else 0), row.peer_name))
        unread_total = sum(row.unread for row in threads)
        await session.commit()
        return InboxOut(
            host=True,
            unread_total=unread_total,
            admin=_presence(user, name="Админ"),
            threads=threads,
        )

    conv = await get_or_create_dm(session, user, admin)
    thread = await _thread_out(session, user, conv, admin)
    await session.commit()
    return InboxOut(
        host=False,
        unread_total=thread.unread,
        admin=_presence(admin, name="Админ"),
        threads=[thread],
    )


@router.post("/open", response_model=ThreadOut)
async def open_thread(
    payload: OpenIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ThreadOut:
    await touch_presence(session, user)
    if user.is_host:
        if payload.user_id is None:
            raise HTTPException(400, "Нужен собеседник")
        peer = await session.get(User, payload.user_id)
        if peer is None or peer.id == user.id:
            raise HTTPException(404, "Не найдено")
    else:
        if payload.user_id is not None:
            raise HTTPException(404, "Не найдено")
        peer = await host_user(session)
    conv = await get_or_create_dm(session, user, peer)
    out = await _thread_out(session, user, conv, peer)
    await session.commit()
    return out


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: int,
    after: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    await require_member(session, user, conversation_id)
    await touch_presence(session, user)
    stmt = select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
    if after > 0:
        rows = (
            await session.execute(stmt.where(ChatMessage.id > after).order_by(ChatMessage.id).limit(200))
        ).scalars().all()
    else:
        rows = list(
            reversed(
                (
                    await session.execute(stmt.order_by(ChatMessage.id.desc()).limit(200))
                ).scalars().all()
            )
        )
    member = await member_row(session, conversation_id, user.id)
    if member is not None:
        member.last_read_at = now_utc()
    await session.commit()
    return [
        MessageOut(
            id=row.id,
            sender_id=row.sender_id,
            mine=row.sender_id == user.id,
            body=row.body,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: int,
    payload: MessageIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    conv = await require_member(session, user, conversation_id)
    body = payload.body.strip()
    if len(body) < 1:
        raise HTTPException(400, "Напиши сообщение")
    stamp = now_utc()
    user.last_seen_at = stamp
    row = ChatMessage(conversation_id=conv.id, sender_id=user.id, body=body[:4000], created_at=stamp)
    session.add(row)
    conv.last_message_at = stamp
    member = await member_row(session, conv.id, user.id)
    if member is not None:
        member.last_read_at = stamp
    await session.commit()
    await session.refresh(row)
    return MessageOut(id=row.id, sender_id=row.sender_id, mine=True, body=row.body, created_at=row.created_at)
