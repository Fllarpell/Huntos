from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ping_slot import PingSlot, ping_scope
from app.models.user import User
from app.models.vacancy import Vacancy
from app.services.auth import ensure_profile
from app.services.google_calendar import google_connected, sync_ping_slot


def default_ping_at() -> datetime:
    tz = ZoneInfo(settings.google_calendar_timezone)
    local = datetime.now(tz)
    slot = local.replace(hour=11, minute=0, second=0, microsecond=0)
    if local >= slot:
        slot = slot + timedelta(days=1)
    if slot.weekday() == 6:
        slot = slot + timedelta(days=1)
    return slot.replace(tzinfo=None)


def slot_out(slot: PingSlot, connected: bool) -> dict:
    return {
        "id": slot.id,
        "thesis_id": slot.thesis_id,
        "label": slot.label,
        "card_count": slot.card_count,
        "ping_at": slot.ping_at.isoformat(timespec="seconds") if slot.ping_at else None,
        "vacancy_ids": list(slot.vacancy_ids or []),
        "google_event_id": slot.google_event_id,
        "google_sync_error": slot.google_sync_error,
        "calendar_connected": connected,
    }


async def ensure_ping_slots(session: AsyncSession, user: User, groups: list[dict]) -> tuple[list[PingSlot], bool]:
    existing = (
        await session.execute(select(PingSlot).where(PingSlot.user_id == user.id))
    ).scalars().all()
    by_scope = {row.scope: row for row in existing}
    live: list[PingSlot] = []
    seen: set[str] = set()

    for group in groups:
        thesis_id = group["thesis_id"]
        scope = ping_scope(thesis_id)
        seen.add(scope)
        items: list[Vacancy] = group["items"]
        label = (group.get("thesis_name") or "").strip() or "без тезиса"
        row = by_scope.get(scope)
        if row is None:
            row = PingSlot(
                user_id=user.id,
                thesis_id=thesis_id,
                scope=scope,
                label=label,
                vacancy_ids=[v.id for v in items],
                card_count=len(items),
                ping_at=default_ping_at(),
            )
            session.add(row)
            await session.flush()
            by_scope[scope] = row
        else:
            ids = [v.id for v in items]
            row.thesis_id = thesis_id
            if row.label != label or row.vacancy_ids != ids:
                row.synced_count = None
            row.label = label
            row.vacancy_ids = ids
            row.card_count = len(items)
            if row.ping_at is None:
                row.ping_at = default_ping_at()
        live.append(row)

    stale = [row for row in existing if row.scope not in seen]
    profile = await ensure_profile(session, user)
    connected = google_connected(profile)
    for row in live:
        await sync_ping_slot(session, profile, row)
    for row in stale:
        row.card_count = 0
        row.vacancy_ids = []
        row.ping_at = None
        await sync_ping_slot(session, profile, row)
        await session.delete(row)
    return live, connected
