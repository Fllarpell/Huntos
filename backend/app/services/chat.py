"""Direct messages. Guests may only talk to the host."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, Conversation, ConversationMember
from app.models.user import User

ONLINE_AFTER = timedelta(seconds=90)
ADMIN_NAME = "Админ"


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def dm_key(left: int, right: int) -> str:
    lo, hi = sorted((left, right))
    return f"{lo}:{hi}"


def is_online(last_seen: datetime | None, at: datetime | None = None) -> bool:
    if last_seen is None:
        return False
    stamp = last_seen.replace(tzinfo=None) if last_seen.tzinfo else last_seen
    return (at or now_utc()) - stamp <= ONLINE_AFTER


def can_direct(actor: User, peer: User) -> bool:
    if actor.id == peer.id:
        return False
    return bool(actor.is_host or peer.is_host)


async def host_user(session: AsyncSession) -> User:
    row = (
        await session.execute(select(User).where(User.is_host.is_(True)).order_by(User.id).limit(1))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Не найдено")
    return row


async def touch_presence(session: AsyncSession, user: User) -> datetime:
    stamp = now_utc()
    user.last_seen_at = stamp
    return stamp


def peer_name(viewer: User, peer: User) -> str:
    if peer.is_host and not viewer.is_host:
        return ADMIN_NAME
    return peer.email


async def get_or_create_dm(session: AsyncSession, actor: User, peer: User) -> Conversation:
    if not can_direct(actor, peer):
        raise HTTPException(404, "Не найдено")
    key = dm_key(actor.id, peer.id)
    existing = (await session.execute(select(Conversation).where(Conversation.dm_key == key))).scalar_one_or_none()
    if existing is not None:
        return existing
    stamp = now_utc()
    try:
        async with session.begin_nested():
            conv = Conversation(dm_key=key, created_at=stamp, updated_at=stamp)
            session.add(conv)
            await session.flush()
            session.add(ConversationMember(conversation_id=conv.id, user_id=actor.id))
            session.add(ConversationMember(conversation_id=conv.id, user_id=peer.id))
            await session.flush()
            return conv
    except IntegrityError:
        found = (await session.execute(select(Conversation).where(Conversation.dm_key == key))).scalar_one_or_none()
        if found is not None:
            return found
        raise


async def require_member(session: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Не найдено")
    member = (
        await session.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(404, "Не найдено")
    if not user.is_host:
        host = await host_user(session)
        members = (
            await session.execute(
                select(ConversationMember.user_id).where(ConversationMember.conversation_id == conversation_id)
            )
        ).scalars().all()
        if host.id not in set(members):
            raise HTTPException(404, "Не найдено")
    return conv


async def other_member(session: AsyncSession, conversation_id: int, user_id: int) -> User:
    peer_id = (
        await session.execute(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id != user_id,
            )
        )
    ).scalar_one_or_none()
    if peer_id is None:
        raise HTTPException(404, "Не найдено")
    peer = await session.get(User, peer_id)
    if peer is None:
        raise HTTPException(404, "Не найдено")
    return peer


def unread_stmt(user_id: int, conversation_id: int, last_read_at: datetime | None) -> Select[tuple[int]]:
    stmt = select(func.count()).select_from(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.sender_id != user_id,
    )
    if last_read_at is not None:
        stmt = stmt.where(ChatMessage.created_at > last_read_at)
    return stmt


async def member_row(session: AsyncSession, conversation_id: int, user_id: int) -> ConversationMember | None:
    return (
        await session.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def last_message(session: AsyncSession, conversation_id: int) -> ChatMessage | None:
    return (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
