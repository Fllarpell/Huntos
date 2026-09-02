from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.sql import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.ping_slot import PingSlot
from app.models.user import User
from app.models.vacancy import PipelineStage, ScoringStatus, Vacancy
from app.schemas.dto import (
    BulkStageUpdate,
    CollisionOut,
    CalendarBoardOut,
    NotesUpdate,
    PipelineColumn,
    ReorderItem,
    StageUpdate,
    TelegramUpdate,
    HhPulseUpdate,
    ClipIn,
    ClipOut,
    VacancyEventPatch,
    VacancyEventWrite,
    VacancyListOut,
    VacancyOut,
    VacancyWrite,
)
from app.services.auth import ensure_profile
from app.services.collisions import collision_snapshot, ranged_meetings
from app.services.contacts import hints_for_vacancy
from app.services.custom_fields import concat_defs, field_bits, merge_defs, normalize_defs
from app.services.deps import event_for_user, get_scope_user, vacancy_for_user
from app.services.hunts import (
    apply_hunt,
    fields_for_vacancy,
    hunt_field_defs,
    hunts_for_vacancy,
    list_hunts,
    pin_vacancy,
    maybe_hunt,
    resolve_hunt,
    set_pins,
)
from app.services.google_calendar import (
    delete_google_for_event,
    google_connected,
    pull_for_user,
    sync_one_vacancy_event,
    sync_vacancy_event,
)
from app.services.nudge import annotate_ping
from app.services.telegram import normalize_telegram_alias
from app.services.vacancy_events import (
    create_event,
    events_payload,
    list_events,
    mirror_next_step,
    refresh_next_step,
    update_event,
)
from app.services.vacancy_write import apply_hh_pulse, apply_pinged, apply_vacancy_write, apply_wrote
from app.services.clipper import clip_vacancy
from app.services.scoring.llm import LLMError
from app.services.scoring.scorer import adapt_resume, generate_cover_letter, generate_telegram_draft, score_vacancy
from app.services.wip import annotate_dwell, enter_stage, touch

router = APIRouter(prefix="/api", tags=["vacancies"])


def _vacancy_out(
    vacancy: Vacancy,
    connected: bool,
    collisions: dict[int, dict] | None = None,
    events: list | None = None,
    company_contacts: list | None = None,
    custom_fields: list | None = None,
    hunts: list | None = None,
    *,
    slim: bool = False,
) -> VacancyOut:
    data = VacancyOut.model_validate(vacancy)
    data.calendar_connected = connected
    data.events = events or []
    data.company_contacts = company_contacts or []
    data.hunts = hunts or []
    hunt = list(custom_fields or [])
    card = normalize_defs(getattr(vacancy, "card_fields", None), strict=False)
    merged = merge_defs(hunt, card)
    data.custom_fields = merged
    data.custom_bits = field_bits(merged, dict(data.custom_values or {}))
    mark = (collisions or {}).get(vacancy.id)
    if mark:
        data.collision_hint = mark["hint"]
        data.collision_peers = mark["peers"]
    due, days = annotate_ping(vacancy)
    data.ping_due = due
    data.silence_days = days
    dwell, stale = annotate_dwell(vacancy)
    data.dwell_days = dwell
    data.dwell_stale = stale
    if slim:
        data.description = None
        data.requirements = None
        data.tasks_html = None
        data.conditions_html = None
        data.important_info = None
        data.cover_letter = None
        data.telegram_message = None
        data.match_rationale = None
        data.adaptation_advice = None
        data.events = []
        data.company_contacts = []
    return data


async def _pull_times(session: AsyncSession, user: User, *, force: bool = False) -> None:
    await pull_for_user(session, user, force=force)
    await session.commit()


async def _board_context(
    session: AsyncSession,
    user: User,
    hunt_id: int | None = None,
) -> tuple[bool, dict[int, dict], list, object]:
    profile = await ensure_profile(session, user)
    _days, _upcoming, index = await collision_snapshot(session, user.id)
    hunt = await maybe_hunt(session, user, hunt_id)
    if hunt is not None:
        fields = hunt_field_defs(hunt, profile)
    else:
        groups = [normalize_defs(row.custom_fields, strict=False) for row in await list_hunts(session, user)]
        fields = concat_defs(groups) or hunt_field_defs(None, profile)
    return google_connected(profile), index, fields, hunt


async def _sync_calendar(session: AsyncSession, user: User, vacancy: Vacancy) -> bool:
    profile = await ensure_profile(session, user)
    connected = google_connected(profile)
    if connected:
        await sync_vacancy_event(session, profile, vacancy)
    return connected


async def _sync_one(session: AsyncSession, user: User, vacancy, event) -> None:
    profile = await ensure_profile(session, user)
    if google_connected(profile):
        await sync_one_vacancy_event(session, profile, vacancy, event)


async def _pack(session: AsyncSession, user: User, vacancy: Vacancy) -> VacancyOut:
    connected, collisions, hunt_fields, _hunt = await _board_context(session, user)
    packed = events_payload(await list_events(session, vacancy.id), connected)
    hints = await hints_for_vacancy(session, user.id, vacancy)
    profile = await ensure_profile(session, user)
    fields = await fields_for_vacancy(session, user, vacancy, hunt=None, profile=profile)
    refs = await hunts_for_vacancy(session, user, vacancy)
    return _vacancy_out(vacancy, connected, collisions, packed, hints, fields or hunt_fields, hunts=refs)


async def _finish(session: AsyncSession, user: User, vacancy: Vacancy, *, sync: bool = False) -> VacancyOut:
    if sync:
        await _sync_calendar(session, user, vacancy)
    await session.commit()
    await session.refresh(vacancy)
    return await _pack(session, user, vacancy)


KANBAN_STAGES = [
    PipelineStage.TO_APPLY,
    PipelineStage.WAITING,
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
    PipelineStage.REJECTED,
]


GRADE_RANK = {
    "head": 6,
    "lead": 5,
    "senior": 4,
    "middle": 3,
    "junior": 2,
    "intern": 1,
}


def _grade_order() -> ColumnElement:
    return case(GRADE_RANK, value=Vacancy.grade, else_=0)


def _best_order():
    now = datetime.now(UTC).replace(tzinfo=None)
    fresh = case(
        (Vacancy.published_at >= now - timedelta(hours=24), 1),
        else_=0,
    )
    has_salary = case(
        (or_(Vacancy.salary_min.isnot(None), Vacancy.salary_max.isnot(None)), 1),
        else_=0,
    )
    amount = func.coalesce(Vacancy.salary_min, Vacancy.salary_max)
    return (
        fresh.desc(),
        has_salary.desc(),
        amount.desc().nullslast(),
        Vacancy.match_score.desc().nullslast(),
        Vacancy.published_at.desc().nullslast(),
    )


def _apply_sort(stmt: Select, sort: str) -> Select:
    if sort == "match":
        return stmt.order_by(Vacancy.match_score.desc().nullslast(), Vacancy.published_at.desc())
    if sort == "recent":
        return stmt.order_by(Vacancy.published_at.desc().nullslast())
    if sort == "grade":
        return stmt.order_by(
            _grade_order().desc(),
            Vacancy.match_score.desc().nullslast(),
            Vacancy.published_at.desc().nullslast(),
        )
    return stmt.order_by(*_best_order())


@router.get("/vacancies", response_model=VacancyListOut)
async def list_vacancies(
    stage: PipelineStage | None = None,
    q: str | None = None,
    sort: str = "best",
    grade: list[str] = Query(default=[]),
    format: list[str] = Query(default=[]),
    nda: str = "any",
    salary: str = "any",
    source: list[str] = Query(default=[]),
    hunt_id: int | None = None,
    limit: int = Query(100, le=300),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyListOut:
    hunt = await maybe_hunt(session, user, hunt_id)
    stmt = select(Vacancy)
    count_stmt = select(func.count(Vacancy.id))
    filters = [Vacancy.user_id == user.id, Vacancy.duplicate_of_id.is_(None)]
    if stage:
        filters.append(Vacancy.pipeline_stage == stage)
    if q:
        raw = q.strip().lower()
        like = f"%{raw}%"
        alias_like = f"%{raw.lstrip('@')}%"
        filters.append(
            func.lower(Vacancy.title).like(like)
            | func.lower(func.coalesce(Vacancy.company, "")).like(like)
            | func.coalesce(Vacancy.company_inn, "").like(alias_like)
            | func.lower(func.coalesce(Vacancy.telegram_alias, "")).like(alias_like)
            | func.lower(func.coalesce(Vacancy.contact_email, "")).like(like)
            | func.coalesce(Vacancy.contact_phone, "").like(like)
            | func.lower(func.coalesce(Vacancy.source_url, "")).like(like)
            | Vacancy.source_id.like(alias_like)
        )
    if grade:
        filters.append(Vacancy.grade.in_(grade))
    if format:
        filters.append(Vacancy.work_format.in_(format))
    company_l = func.lower(func.trim(Vacancy.company))
    if nda == "nda":
        filters.append(company_l == "nda")
    elif nda == "named":
        filters.append(or_(Vacancy.company.is_(None), company_l != "nda"))
    if salary == "known":
        filters.append(or_(Vacancy.salary_min.isnot(None), Vacancy.salary_max.isnot(None)))
    elif salary == "hidden":
        filters.append(Vacancy.salary_min.is_(None) & Vacancy.salary_max.is_(None))
    if source:
        filters.append(Vacancy.source.in_(source))
    stmt = stmt.where(*filters)
    count_stmt = count_stmt.where(*filters)
    if hunt is not None:
        stmt = apply_hunt(stmt, hunt)
        count_stmt = apply_hunt(count_stmt, hunt)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(_apply_sort(stmt, sort).offset(offset).limit(limit))).scalars().all()
    connected, collisions, hunt_fields, _hunt = await _board_context(session, user, hunt_id)
    return VacancyListOut(
        items=[_vacancy_out(row, connected, collisions, slim=True, custom_fields=hunt_fields) for row in rows],
        total=total,
    )


@router.post("/vacancies", response_model=VacancyOut)
async def create_vacancy(
    payload: VacancyWrite,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    now = datetime.now(UTC).replace(tzinfo=None)
    vacancy = Vacancy(
        user_id=user.id,
        source="manual",
        source_id=uuid4().hex,
        title="Новая вакансия",
        pipeline_stage=PipelineStage.INBOX,
        scoring_status=ScoringStatus.PENDING,
        published_at=now,
        last_seen_at=now,
        stage_entered_at=now,
        skills=[],
        tags=[],
        extra_sources=[],
    )
    apply_vacancy_write(vacancy, payload)
    if vacancy.pipeline_stage != PipelineStage.INBOX:
        touch(vacancy)
    from app.services.fingerprint import vacancy_fingerprint

    vacancy.fingerprint = vacancy_fingerprint(vacancy.title, vacancy.company)
    session.add(vacancy)
    await session.flush()
    if payload.hunt_id is not None:
        await resolve_hunt(session, user, payload.hunt_id)
        await pin_vacancy(session, payload.hunt_id, vacancy.id)
    if vacancy.next_step_at is not None:
        await mirror_next_step(session, vacancy)
    return await _finish(session, user, vacancy, sync=True)


@router.post("/vacancies/clip", response_model=ClipOut)
async def clip_job(
    payload: ClipIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ClipOut:
    try:
        vacancy, action = await clip_vacancy(
            session,
            user.id,
            url=payload.url,
            title=payload.title,
            company=payload.company,
            description=payload.description,
            salary_raw=payload.salary_raw,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if payload.hunt_id is not None:
        await resolve_hunt(session, user, payload.hunt_id)
        await pin_vacancy(session, payload.hunt_id, vacancy.id)
    packed = await _finish(session, user, vacancy)
    return ClipOut(created=action == "new", merged=action != "new", vacancy=packed)


@router.patch("/vacancies/{vacancy_id}", response_model=VacancyOut)
async def update_vacancy(
    vacancy_id: int,
    payload: VacancyWrite,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    changed = payload.model_dump(exclude_unset=True)
    apply_vacancy_write(vacancy, payload)
    if "next_step_at" in changed or "next_step_kind" in changed:
        await mirror_next_step(session, vacancy)
        return await _finish(session, user, vacancy, sync=True)
    return await _finish(session, user, vacancy)


@router.get("/vacancies/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    return await _pack(session, user, vacancy)


class VacancyHuntsIn(BaseModel):
    hunt_ids: list[int] = Field(default_factory=list)


@router.put("/vacancies/{vacancy_id}/hunts", response_model=VacancyOut)
async def update_vacancy_hunts(
    vacancy_id: int,
    payload: VacancyHuntsIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    await set_pins(session, user, vacancy, payload.hunt_ids)
    return await _finish(session, user, vacancy)


@router.post("/vacancies/{vacancy_id}/events", response_model=VacancyOut)
async def add_vacancy_event(
    vacancy_id: int,
    payload: VacancyEventWrite,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    event = await create_event(
        session,
        vacancy,
        kind=payload.kind,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        label=payload.label,
    )
    await _sync_one(session, user, vacancy, event)
    return await _finish(session, user, vacancy)


@router.patch("/events/{event_id}", response_model=VacancyOut)
async def patch_vacancy_event(
    event_id: int,
    payload: VacancyEventPatch,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    event, vacancy = await event_for_user(session, user, event_id)
    data = payload.model_dump(exclude_unset=True)
    await update_event(
        session,
        vacancy,
        event,
        kind=data.get("kind"),
        starts_at=data.get("starts_at"),
        ends_at=data.get("ends_at"),
        label=data["label"] if "label" in data else ...,
    )
    await _sync_one(session, user, vacancy, event)
    return await _finish(session, user, vacancy)


@router.delete("/events/{event_id}", response_model=VacancyOut)
async def delete_vacancy_event(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    event, vacancy = await event_for_user(session, user, event_id)
    profile = await ensure_profile(session, user)
    await delete_google_for_event(profile, event)
    await session.delete(event)
    await session.flush()
    refresh_next_step(vacancy, await list_events(session, vacancy.id))
    return await _finish(session, user, vacancy)


@router.patch("/vacancies/{vacancy_id}/stage", response_model=VacancyOut)
async def update_stage(
    vacancy_id: int,
    payload: StageUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    enter_stage(vacancy, payload.stage)
    if payload.position is not None:
        vacancy.pipeline_position = payload.position
    if payload.hunt_id is not None:
        await resolve_hunt(session, user, payload.hunt_id)
        await pin_vacancy(session, payload.hunt_id, vacancy.id)
    return await _finish(session, user, vacancy)


@router.patch("/vacancies/{vacancy_id}/notes", response_model=VacancyOut)
async def update_notes(
    vacancy_id: int,
    payload: NotesUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    vacancy.notes = payload.notes
    return await _finish(session, user, vacancy)


@router.patch("/vacancies/{vacancy_id}/telegram", response_model=VacancyOut)
async def update_telegram(
    vacancy_id: int,
    payload: TelegramUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    vacancy.telegram_alias = normalize_telegram_alias(payload.telegram_alias)
    return await _finish(session, user, vacancy)


@router.post("/vacancies/{vacancy_id}/score", response_model=VacancyOut)
async def rescore(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    vacancy.scoring_status = ScoringStatus.PENDING
    await session.commit()
    vacancy = await score_vacancy(session, vacancy)
    return await _pack(session, user, vacancy)


@router.post("/vacancies/{vacancy_id}/adapt")
async def adapt(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    try:
        data = await adapt_resume(session, vacancy)
    except LLMError as exc:
        raise HTTPException(400, str(exc)) from exc
    return data


@router.post("/vacancies/{vacancy_id}/cover-letter")
async def cover_letter(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    try:
        text = await generate_cover_letter(session, vacancy)
    except LLMError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"cover_letter": text}


@router.post("/vacancies/{vacancy_id}/telegram-draft")
async def telegram_draft(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    try:
        text = await generate_telegram_draft(session, vacancy)
    except LLMError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"telegram_message": text}


@router.post("/vacancies/{vacancy_id}/wrote", response_model=VacancyOut)
async def mark_wrote(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    apply_wrote(vacancy)
    return await _finish(session, user, vacancy)


@router.post("/vacancies/{vacancy_id}/pinged", response_model=VacancyOut)
async def mark_pinged(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    if vacancy.pipeline_stage != PipelineStage.WAITING:
        raise HTTPException(400, "Пинг только из «жду ответа»")
    apply_pinged(vacancy)
    return await _finish(session, user, vacancy)


@router.post("/vacancies/{vacancy_id}/hh-pulse", response_model=VacancyOut)
async def mark_hh_pulse(
    vacancy_id: int,
    payload: HhPulseUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> VacancyOut:
    vacancy = await vacancy_for_user(session, user, vacancy_id)
    apply_hh_pulse(vacancy, payload.pulse)
    return await _finish(session, user, vacancy)


@router.post("/vacancies/bulk-stage")
async def bulk_stage(
    payload: BulkStageUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    if payload.hunt_id is not None:
        await resolve_hunt(session, user, payload.hunt_id)
    moved = 0
    for vacancy_id in payload.ids:
        vacancy = await session.get(Vacancy, vacancy_id)
        if not vacancy or vacancy.user_id != user.id:
            continue
        enter_stage(vacancy, payload.stage)
        if payload.hunt_id is not None:
            await pin_vacancy(session, payload.hunt_id, vacancy.id)
        moved += 1
    await session.commit()
    return {"ok": True, "moved": moved}


@router.get("/calendar/collisions", response_model=CollisionOut)
async def calendar_collisions(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> CollisionOut:
    await _pull_times(session, user)
    days, upcoming, _index = await collision_snapshot(session, user.id)
    return CollisionOut.model_validate({"days": days, "upcoming": upcoming})


@router.get("/calendar", response_model=CalendarBoardOut)
async def calendar_board(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> CalendarBoardOut:
    await _pull_times(session, user, force=True)
    days, _upcoming, _index = await collision_snapshot(session, user.id)
    meetings = await ranged_meetings(session, user.id)
    slots = (
        await session.execute(
            select(PingSlot).where(
                PingSlot.user_id == user.id,
                PingSlot.ping_at.isnot(None),
                PingSlot.card_count > 0,
            )
        )
    ).scalars().all()
    profile = await ensure_profile(session, user)
    return CalendarBoardOut(
        calendar_connected=google_connected(profile),
        calendar_ready=bool(profile.google_calendar_id),
        collisions=days,
        meetings=meetings,
        ping_slots=[
            {
                "id": row.id,
                "thesis_id": row.thesis_id,
                "label": row.label,
                "card_count": row.card_count,
                "ping_at": row.ping_at,
                "vacancy_ids": list(row.vacancy_ids or []),
            }
            for row in slots
        ],
    )


@router.get("/pipeline", response_model=list[PipelineColumn])
async def pipeline(
    hunt_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> list[PipelineColumn]:
    hunt = await maybe_hunt(session, user, hunt_id)
    stmt = (
        select(Vacancy)
        .where(
            Vacancy.user_id == user.id,
            Vacancy.duplicate_of_id.is_(None),
            Vacancy.pipeline_stage.in_(KANBAN_STAGES),
        )
        .order_by(Vacancy.next_step_at.asc().nullslast(), *_best_order())
    )
    stmt = apply_hunt(stmt, hunt)
    result = await session.execute(stmt)
    grouped: dict[PipelineStage, list[Vacancy]] = {stage: [] for stage in KANBAN_STAGES}
    for row in result.scalars():
        grouped[row.pipeline_stage].append(row)
    connected, collisions, hunt_fields, _hunt = await _board_context(session, user, hunt_id)
    return [
        PipelineColumn(stage=stage, items=[_vacancy_out(v, connected, collisions, slim=True, custom_fields=hunt_fields) for v in items])
        for stage, items in grouped.items()
    ]


@router.post("/pipeline/reorder")
async def reorder(
    items: list[ReorderItem],
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    for item in items:
        vacancy = await session.get(Vacancy, item.id)
        if not vacancy or vacancy.user_id != user.id:
            continue
        enter_stage(vacancy, item.stage)
        vacancy.pipeline_position = item.position
    await session.commit()
    return {"ok": True}
