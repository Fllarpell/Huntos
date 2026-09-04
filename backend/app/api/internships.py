from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.internship_monitor import InternshipMonitor
from app.models.internship_track import InternshipTrack
from app.models.user import User
from app.services.company_icon import fallback_company_icon
from app.services.deps import get_scope_user
from app.services.internship_catalog import program_by_slug, programs
from app.services.internship_monitor import monitor_map, refresh_internship_statuses

router = APIRouter(prefix="/api/internships", tags=["internships"])

TRACK_STATUSES = frozenset({"watch", "applied", "screening", "offer", "rejected", "skip"})


class InternshipProgramOut(BaseModel):
    slug: str
    name: str
    company: str
    url: str
    kind: str
    catalog_status: str
    hint: str = ""
    logo_url: str | None = None


class InternshipTrackOut(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: str | None = None
    updated_at: str | None = None


class InternshipRowOut(InternshipProgramOut):
    live_status: str | None = None
    checked_at: str | None = None
    check_error: str | None = None
    signal: str | None = None
    track: InternshipTrackOut = Field(default_factory=InternshipTrackOut)


class InternshipTrackIn(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: str | None = None


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


def _track_out(row: InternshipTrack | None) -> InternshipTrackOut:
    if row is None:
        return InternshipTrackOut()
    return InternshipTrackOut(
        status=row.track_status,
        notes=row.notes,
        applied_at=_iso(row.applied_at),
        updated_at=_iso(row.updated_at),
    )


def _row_out(
    program,
    track: InternshipTrack | None,
    monitor: InternshipMonitor | None,
) -> InternshipRowOut:
    return InternshipRowOut(
        slug=program.slug,
        name=program.name,
        company=program.company,
        url=program.url,
        kind=program.kind,
        catalog_status=program.catalog_status,
        hint=program.hint,
        logo_url=fallback_company_icon(program.company, program.url),
        live_status=monitor.live_status if monitor else None,
        checked_at=_iso(monitor.checked_at) if monitor else None,
        check_error=monitor.check_error if monitor else None,
        signal=monitor.signal if monitor else None,
        track=_track_out(track),
    )


@router.get("", response_model=list[InternshipRowOut])
async def list_internships(
    kind: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> list[InternshipRowOut]:
    if kind is not None and kind not in {"internship", "school"}:
        raise HTTPException(400, "kind должен быть internship или school")
    rows = (
        await session.execute(select(InternshipTrack).where(InternshipTrack.user_id == user.id))
    ).scalars().all()
    by_slug = {row.program_slug: row for row in rows}
    monitors = await monitor_map(session)
    return [_row_out(program, by_slug.get(program.slug), monitors.get(program.slug)) for program in programs(kind)]


@router.put("/{slug}", response_model=InternshipRowOut)
async def upsert_internship_track(
    slug: str,
    payload: InternshipTrackIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> InternshipRowOut:
    program = program_by_slug(slug)
    if program is None:
        raise HTTPException(404, "Программа не найдена")
    monitors = await monitor_map(session)
    monitor = monitors.get(slug)
    status = (payload.status or "").strip() or None
    if status is not None and status not in TRACK_STATUSES:
        raise HTTPException(400, f"status: {', '.join(sorted(TRACK_STATUSES))}")
    notes = (payload.notes or "").strip() or None
    applied_at = _parse_applied(payload.applied_at)
    now = datetime.now(UTC).replace(tzinfo=None)
    row = (
        await session.execute(
            select(InternshipTrack).where(
                InternshipTrack.user_id == user.id,
                InternshipTrack.program_slug == slug,
            )
        )
    ).scalar_one_or_none()
    if status is None and notes is None and applied_at is None:
        if row is not None:
            await session.delete(row)
            await session.commit()
        return _row_out(program, None, monitor)
    if row is None:
        row = InternshipTrack(
            user_id=user.id,
            program_slug=slug,
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
    return _row_out(program, row, monitor)
