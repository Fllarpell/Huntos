from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.hunt_thesis import HuntThesis
from app.models.outreach_wave import OutreachWave
from app.models.user import User
from app.models.vacancy import PipelineStage, Vacancy
from app.schemas.dto import VacancyOut
from app.services.deps import get_scope_user
from app.services.auth import ensure_profile
from app.services.custom_fields import normalize_defs
from app.services.google_calendar import google_connected, pull_for_user, sync_ping_slot
from app.services.hunts import inbox_count, list_hunts, pin_many, save_hunt_fields, seed_fields_on_create
from app.services.nudge import annotate_ping, nudge_queue
from app.services.wip import annotate_dwell
from app.services.ping_slot import ensure_ping_slots, ping_scope, slot_out
from app.services.thesis import (
    PACK_DEFAULT,
    PACK_LIST,
    PACK_MAX,
    matching_vacancies,
    rank_inbox_pack,
    refresh_thesis,
)
from app.services.vacancy_write import apply_pinged, apply_wrote
from app.services.hunt_desk import hunt_desk as desk_snapshot

router = APIRouter(prefix="/api", tags=["hunt"])


class ThesisIn(BaseModel):
    name: str = "Текущий поиск"
    role_query: str = ""
    grades: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    no_nda: bool = False
    days: int = 14
    min_sample: int = 8
    min_median_match: int = 55
    enabled: bool = True
    custom_fields: list | None = None


class ThesisOut(ThesisIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_verdict: str | None = None
    last_reason: str | None = None
    last_evaluated_at: datetime | None = None
    stats: dict | None = None
    last_wave: dict | None = None


def _fields(payload: ThesisIn) -> dict:
    return {
        "name": (payload.name or "").strip() or "Текущий поиск",
        "role_query": (payload.role_query or "").strip(),
        "grades": payload.grades or [],
        "formats": payload.formats or [],
        "salary_min": payload.salary_min,
        "no_nda": payload.no_nda,
        "days": max(3, min(60, payload.days or 14)),
        "min_sample": max(3, min(40, payload.min_sample or 8)),
        "min_median_match": max(20, min(90, payload.min_median_match or 55)),
        "enabled": payload.enabled,
    }


async def _apply_fields(session: AsyncSession, row: HuntThesis, payload: ThesisIn) -> None:
    if payload.custom_fields is None:
        return
    await save_hunt_fields(session, row, payload.custom_fields)


async def _thesis_for_user(session: AsyncSession, user: User, thesis_id: int) -> HuntThesis:
    row = await session.get(HuntThesis, thesis_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Тезис не найден")
    return row


async def _last_wave(session: AsyncSession, thesis_id: int) -> dict | None:
    row = (
        await session.execute(
            select(OutreachWave)
            .where(OutreachWave.thesis_id == thesis_id)
            .order_by(OutreachWave.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "wrote_count": row.wrote_count,
        "drafted_count": row.drafted_count,
        "size": len(row.vacancy_ids or []),
        "sent_at": row.sent_at,
    }


async def _thesis_out(session: AsyncSession, row: HuntThesis, stats: dict | None = None) -> ThesisOut:
    data = ThesisOut.model_validate(row)
    if stats is None:
        stats = await refresh_thesis(session, row)
    data.stats = stats
    data.last_verdict = stats["verdict"]
    data.last_reason = stats["reason"]
    data.last_wave = await _last_wave(session, row.id)
    data.custom_fields = normalize_defs(row.custom_fields, strict=False)
    return data


class WaveIds(BaseModel):
    ids: list[int] = Field(default_factory=list)


class DensityDay(BaseModel):
    date: str
    new: int


class HuntDeskOut(BaseModel):
    inbox_total: int
    waiting_total: int
    density: list[DensityDay] = Field(default_factory=list)


@router.get("/hunt/desk", response_model=HuntDeskOut)
async def get_hunt_desk(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> HuntDeskOut:
    return HuntDeskOut.model_validate(await desk_snapshot(session, user.id))


class HuntItemOut(BaseModel):
    id: int
    name: str
    enabled: bool = True
    inbox_count: int = 0
    custom_fields: list = Field(default_factory=list)


class HuntListOut(BaseModel):
    items: list[HuntItemOut] = Field(default_factory=list)
    active_hunt_id: int | None = None


class HuntActiveIn(BaseModel):
    hunt_id: int | None = None


class HuntFieldsIn(BaseModel):
    custom_fields: list = Field(default_factory=list)


@router.get("/hunts", response_model=HuntListOut)
async def get_hunts(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> HuntListOut:
    profile = await ensure_profile(session, user)
    items: list[HuntItemOut] = []
    for row in await list_hunts(session, user):
        items.append(
            HuntItemOut(
                id=row.id,
                name=row.name,
                enabled=row.enabled,
                inbox_count=await inbox_count(session, row),
                custom_fields=normalize_defs(row.custom_fields, strict=False),
            )
        )
    active = profile.active_hunt_id
    if active is not None and not any(item.id == active for item in items):
        active = None
    return HuntListOut(items=items, active_hunt_id=active)


@router.patch("/hunts/active", response_model=HuntListOut)
async def set_active_hunt(
    payload: HuntActiveIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> HuntListOut:
    profile = await ensure_profile(session, user)
    if payload.hunt_id is not None:
        await _thesis_for_user(session, user, payload.hunt_id)
    profile.active_hunt_id = payload.hunt_id
    await session.commit()
    return await get_hunts(session, user)


@router.put("/theses/{thesis_id}/fields", response_model=ThesisOut)
async def update_thesis_fields(
    thesis_id: int,
    payload: HuntFieldsIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ThesisOut:
    row = await _thesis_for_user(session, user, thesis_id)
    try:
        await save_hunt_fields(session, row, payload.custom_fields)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await session.commit()
    await session.refresh(row)
    return await _thesis_out(session, row)


class WavePackOut(BaseModel):
    inbox_total: int
    suggested_ids: list[int]
    items: list[VacancyOut]
    pack_default: int = PACK_DEFAULT
    pack_max: int = PACK_MAX
    last_wave: dict | None = None


@router.get("/theses", response_model=list[ThesisOut])
async def list_theses(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> list[ThesisOut]:
    rows = (
        await session.execute(select(HuntThesis).where(HuntThesis.user_id == user.id).order_by(HuntThesis.id))
    ).scalars().all()
    out: list[ThesisOut] = []
    for row in rows:
        out.append(await _thesis_out(session, row))
    return out


@router.post("/theses", response_model=ThesisOut)
async def create_thesis(
    payload: ThesisIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ThesisOut:
    row = HuntThesis(user_id=user.id, **_fields(payload))
    session.add(row)
    await session.flush()
    profile = await ensure_profile(session, user)
    await seed_fields_on_create(session, user, row, profile)
    try:
        await _apply_fields(session, row, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await session.commit()
    await session.refresh(row)
    return await _thesis_out(session, row)


@router.put("/theses/{thesis_id}", response_model=ThesisOut)
async def update_thesis(
    thesis_id: int,
    payload: ThesisIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ThesisOut:
    row = await _thesis_for_user(session, user, thesis_id)
    for key, value in _fields(payload).items():
        setattr(row, key, value)
    try:
        await _apply_fields(session, row, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await session.commit()
    await session.refresh(row)
    return await _thesis_out(session, row)


@router.delete("/theses/{thesis_id}")
async def delete_thesis(
    thesis_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    row = await _thesis_for_user(session, user, thesis_id)
    profile = await ensure_profile(session, user)
    if profile.active_hunt_id == row.id:
        profile.active_hunt_id = None
    await session.delete(row)
    await session.commit()
    return {"ok": True}


@router.get("/theses/{thesis_id}/wave-pack", response_model=WavePackOut)
async def wave_pack(
    thesis_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> WavePackOut:
    thesis = await _thesis_for_user(session, user, thesis_id)
    inbox = rank_inbox_pack(await matching_vacancies(session, thesis))
    suggested = inbox[:PACK_DEFAULT]
    visible = inbox[:PACK_LIST]
    return WavePackOut(
        inbox_total=len(inbox),
        suggested_ids=[row.id for row in suggested],
        items=[VacancyOut.model_validate(row) for row in visible],
        last_wave=await _last_wave(session, thesis.id),
    )


@router.post("/theses/{thesis_id}/wave/wrote")
async def wave_wrote(
    thesis_id: int,
    payload: WaveIds,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    thesis = await _thesis_for_user(session, user, thesis_id)
    ids = list(dict.fromkeys(payload.ids))[:PACK_MAX]
    if not ids:
        raise HTTPException(400, "Выбери карточки в пачке")
    moved: list[Vacancy] = []
    for vacancy_id in ids:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None or vacancy.user_id != user.id:
            continue
        if vacancy.pipeline_stage not in {PipelineStage.INBOX, PipelineStage.TO_APPLY}:
            continue
        apply_wrote(vacancy)
        moved.append(vacancy)
    if not moved:
        raise HTTPException(400, "Некого отмечать — карточки уже не в работе")
    wave = OutreachWave(
        user_id=user.id,
        thesis_id=thesis.id,
        vacancy_ids=[row.id for row in moved],
        wrote_count=len(moved),
        drafted_count=sum(1 for row in moved if row.telegram_message),
        sent_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(wave)
    await pin_many(session, thesis.id, [row.id for row in moved])
    await session.commit()
    await session.refresh(wave)
    return {
        "ok": True,
        "wrote": len(moved),
        "wave": await _last_wave(session, thesis.id),
    }


def _nudge_card(vacancy: Vacancy) -> VacancyOut:
    data = VacancyOut.model_validate(vacancy)
    due, days = annotate_ping(vacancy)
    data.ping_due = due
    data.silence_days = days
    dwell, stale = annotate_dwell(vacancy)
    data.dwell_days = dwell
    data.dwell_stale = stale
    return data


async def _nudge_payload(session: AsyncSession, user: User) -> dict:
    await pull_for_user(session, user)
    snapshot = await nudge_queue(session, user.id)
    slots, connected = await ensure_ping_slots(session, user, snapshot["groups"])
    await session.commit()
    by_scope = {row.scope: row for row in slots}
    return {
        "after_days": snapshot["after_days"],
        "total": snapshot["total"],
        "calendar_connected": connected,
        "groups": [
            {
                "thesis_id": group["thesis_id"],
                "thesis_name": group["thesis_name"],
                "items": [_nudge_card(row) for row in group["items"]],
                "slot": slot_out(by_scope[ping_scope(group["thesis_id"])], connected)
                if ping_scope(group["thesis_id"]) in by_scope
                else None,
            }
            for group in snapshot["groups"]
        ],
    }


class NudgeSlotIn(BaseModel):
    thesis_id: int | None = None
    ping_at: datetime | None = None


@router.get("/nudge")
async def get_nudge(
    hunt_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    data = await _nudge_payload(session, user)
    if hunt_id is not None:
        data["groups"] = [group for group in data["groups"] if group["thesis_id"] == hunt_id]
        data["total"] = sum(len(group["items"]) for group in data["groups"])
    return data


@router.patch("/nudge/slot")
async def patch_nudge_slot(
    payload: NudgeSlotIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    snapshot = await nudge_queue(session, user.id)
    slots, _connected = await ensure_ping_slots(session, user, snapshot["groups"])
    scope = ping_scope(payload.thesis_id)
    row = next((item for item in slots if item.scope == scope), None)
    if row is None:
        raise HTTPException(404, "Очередь пинга по этому тезису ещё не созрела")
    row.ping_at = payload.ping_at
    if payload.ping_at is None:
        row.synced_ping_at = None
    profile = await ensure_profile(session, user)
    await sync_ping_slot(session, profile, row)
    await session.commit()
    return slot_out(row, google_connected(profile))


@router.post("/nudge/pinged")
async def nudge_pinged(
    payload: WaveIds,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        raise HTTPException(400, "Выбери кого пингануть")
    moved = 0
    for vacancy_id in ids:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None or vacancy.user_id != user.id:
            continue
        if vacancy.pipeline_stage != PipelineStage.WAITING:
            continue
        apply_pinged(vacancy)
        moved += 1
    if not moved:
        raise HTTPException(400, "Некого пинговать")
    await session.flush()
    data = await _nudge_payload(session, user)
    return {"ok": True, "pinged": moved, "total": data["total"]}
