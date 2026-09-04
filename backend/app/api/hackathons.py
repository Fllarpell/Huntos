from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.hackathon_event import HackathonEvent
from app.models.hackathon_track import HackathonTrack
from app.models.user import User
from app.services.deps import get_scope_user
from app.services.hackathons_parse import SOURCE_LABELS
from app.services.hackathons_sync import compute_is_new, refresh_hackathons

router = APIRouter(prefix="/api/hackathons", tags=["hackathons"])

TRACK_STATUSES = frozenset({"watch", "applied", "participating", "won", "rejected", "skip"})


class HackathonTrackOut(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: str | None = None
    updated_at: str | None = None


class HackathonRowOut(BaseModel):
    id: int
    source: str
    source_label: str
    source_id: str
    title: str
    url: str
    description: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    registration_status: str
    event_status: str
    format: str | None = None
    location: str | None = None
    tags: str | None = None
    prize_text: str | None = None
    organizer: str | None = None
    image_url: str | None = None
    is_new: bool = False
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    track: HackathonTrackOut = Field(default_factory=HackathonTrackOut)


class HackathonTrackIn(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: str | None = None


class HackathonSyncOut(BaseModel):
    created: int
    updated: int
    errors: int
    total: int


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _parse_applied(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if len(text) == 10:
        text = f"{text}T00:00:00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, "Некорректная дата applied_at") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _track_out(row: HackathonTrack | None) -> HackathonTrackOut:
    if row is None:
        return HackathonTrackOut()
    return HackathonTrackOut(
        status=row.track_status,
        notes=row.notes,
        applied_at=_iso(row.applied_at),
        updated_at=_iso(row.updated_at),
    )


def _row_out(event: HackathonEvent, track: HackathonTrack | None) -> HackathonRowOut:
    return HackathonRowOut(
        id=event.id,
        source=event.source,
        source_label=SOURCE_LABELS.get(event.source, event.source),
        source_id=event.source_id,
        title=event.title,
        url=event.url,
        description=event.description,
        starts_at=_iso(event.starts_at),
        ends_at=_iso(event.ends_at),
        registration_status=event.registration_status,
        event_status=event.event_status,
        format=event.format,
        location=event.location,
        tags=event.tags,
        prize_text=event.prize_text,
        organizer=event.organizer,
        image_url=event.image_url,
        is_new=compute_is_new(
            event_status=event.event_status,
            registration_status=event.registration_status,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
        ),
        first_seen_at=_iso(event.first_seen_at),
        last_seen_at=_iso(event.last_seen_at),
        track=_track_out(track),
    )


@router.get("", response_model=list[HackathonRowOut])
async def list_hackathons(
    status: str | None = None,
    registration: str | None = None,
    source: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> list[HackathonRowOut]:
    query = select(HackathonEvent)
    if status:
        query = query.where(HackathonEvent.event_status == status)
    if registration:
        query = query.where(HackathonEvent.registration_status == registration)
    if source:
        query = query.where(HackathonEvent.source == source)
    events = (await session.execute(query)).scalars().all()
    tracks = (
        await session.execute(select(HackathonTrack).where(HackathonTrack.user_id == user.id))
    ).scalars().all()
    by_event = {row.event_id: row for row in tracks}

    def sort_key(event: HackathonEvent) -> tuple:
        open_rank = 0 if event.registration_status == "open" else 1
        finished = 1 if event.event_status == "finished" else 0
        start = event.starts_at or event.ends_at or datetime.max.replace(tzinfo=None)
        return (finished, open_rank, start, event.title.lower())

    events = sorted(events, key=sort_key)
    return [_row_out(event, by_event.get(event.id)) for event in events]


@router.post("/sync", response_model=HackathonSyncOut)
async def sync_hackathons(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> HackathonSyncOut:
    del user
    stats = await refresh_hackathons(session)
    return HackathonSyncOut(**stats)


@router.put("/{event_id}", response_model=HackathonRowOut)
async def upsert_hackathon_track(
    event_id: int,
    payload: HackathonTrackIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> HackathonRowOut:
    event = await session.get(HackathonEvent, event_id)
    if event is None:
        raise HTTPException(404, "Хакатон не найден")
    status = (payload.status or "").strip() or None
    if status is not None and status not in TRACK_STATUSES:
        raise HTTPException(400, f"status: {', '.join(sorted(TRACK_STATUSES))}")
    notes = (payload.notes or "").strip() or None
    applied_at = _parse_applied(payload.applied_at)
    now = datetime.now(UTC).replace(tzinfo=None)
    row = (
        await session.execute(
            select(HackathonTrack).where(
                HackathonTrack.user_id == user.id,
                HackathonTrack.event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if status is None and notes is None and applied_at is None:
        if row is not None:
            await session.delete(row)
            await session.commit()
        return _row_out(event, None)
    if row is None:
        row = HackathonTrack(
            user_id=user.id,
            event_id=event_id,
            track_status=status,
            notes=notes,
            applied_at=applied_at,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.track_status = status
        row.notes = notes
        row.applied_at = applied_at
        row.updated_at = now
    await session.commit()
    await session.refresh(row)
    return _row_out(event, row)
