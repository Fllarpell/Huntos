from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql import ColumnElement

from app.models.hunt_pin import HuntPin
from app.models.hunt_thesis import HuntThesis
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.vacancy import PipelineStage, Vacancy
from app.services.custom_fields import concat_defs, normalize_defs


def match_filters(thesis: HuntThesis, *, window: bool = False) -> list[ColumnElement]:
    filters: list[ColumnElement] = [
        Vacancy.user_id == thesis.user_id,
        Vacancy.duplicate_of_id.is_(None),
        Vacancy.pipeline_stage != PipelineStage.TRASH,
    ]
    if window:
        from datetime import UTC, datetime, timedelta

        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=max(3, thesis.days or 14))
        filters.append(
            or_(Vacancy.published_at >= since, and_(Vacancy.published_at.is_(None), Vacancy.created_at >= since))
        )
    q = (thesis.role_query or "").strip()
    if q:
        like = f"%{q.lower()}%"
        filters.append(
            func.lower(Vacancy.title).like(like)
            | func.lower(func.coalesce(Vacancy.company, "")).like(like)
            | func.lower(func.coalesce(Vacancy.description, "")).like(like)
        )
    if thesis.grades:
        filters.append(Vacancy.grade.in_(list(thesis.grades)))
    if thesis.formats:
        filters.append(Vacancy.work_format.in_(list(thesis.formats)))
    if thesis.salary_min:
        filters.append(func.coalesce(Vacancy.salary_min, Vacancy.salary_max) >= thesis.salary_min)
    if thesis.no_nda:
        filters.append(func.lower(func.trim(func.coalesce(Vacancy.company, ""))) != "nda")
    return filters


def membership_clause(thesis: HuntThesis) -> ColumnElement:
    pinned = Vacancy.id.in_(select(HuntPin.vacancy_id).where(HuntPin.hunt_id == thesis.id))
    return or_(and_(*match_filters(thesis, window=False)), pinned)


def apply_hunt(stmt: Select, thesis: HuntThesis | None) -> Select:
    if thesis is None:
        return stmt
    return stmt.where(membership_clause(thesis))


def vacancy_matches(thesis: HuntThesis, vacancy: Vacancy, *, window: bool = False) -> bool:
    if vacancy.user_id != thesis.user_id or vacancy.duplicate_of_id is not None:
        return False
    if vacancy.pipeline_stage == PipelineStage.TRASH:
        return False
    if window:
        from datetime import UTC, datetime, timedelta

        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=max(3, thesis.days or 14))
        published = vacancy.published_at or vacancy.created_at
        if published is None or published < since:
            return False
    q = (thesis.role_query or "").strip().lower()
    if q:
        hay = f"{vacancy.title} {vacancy.company or ''} {vacancy.description or ''}".lower()
        if q not in hay:
            return False
    if thesis.grades and vacancy.grade not in thesis.grades:
        return False
    if thesis.formats and vacancy.work_format not in thesis.formats:
        return False
    if thesis.salary_min:
        pay = vacancy.salary_min if vacancy.salary_min is not None else vacancy.salary_max
        if pay is None or pay < thesis.salary_min:
            return False
    if thesis.no_nda and (vacancy.company or "").strip().lower() == "nda":
        return False
    return True


async def hunt_for_user(session: AsyncSession, user: User, hunt_id: int) -> HuntThesis:
    row = await session.get(HuntThesis, hunt_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Охота не найдена")
    return row


async def list_hunts(session: AsyncSession, user: User) -> list[HuntThesis]:
    return list(
        (await session.execute(select(HuntThesis).where(HuntThesis.user_id == user.id).order_by(HuntThesis.id)))
        .scalars()
        .all()
    )


async def resolve_hunt(session: AsyncSession, user: User, hunt_id: int | None) -> HuntThesis | None:
    if hunt_id is None:
        return None
    return await hunt_for_user(session, user, hunt_id)


async def maybe_hunt(session: AsyncSession, user: User, hunt_id: int | None) -> HuntThesis | None:
    if hunt_id is None:
        return None
    row = await session.get(HuntThesis, hunt_id)
    if row is None or row.user_id != user.id:
        return None
    return row


async def inbox_count(session: AsyncSession, thesis: HuntThesis) -> int:
    total = (
        await session.execute(
            select(func.count(Vacancy.id)).where(
                membership_clause(thesis),
                Vacancy.pipeline_stage == PipelineStage.INBOX,
            )
        )
    ).scalar_one()
    return int(total or 0)


async def pin_vacancy(session: AsyncSession, hunt_id: int, vacancy_id: int) -> HuntPin:
    existing = (
        await session.execute(
            select(HuntPin).where(HuntPin.hunt_id == hunt_id, HuntPin.vacancy_id == vacancy_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = HuntPin(hunt_id=hunt_id, vacancy_id=vacancy_id)
    session.add(row)
    await session.flush()
    return row


async def pin_many(session: AsyncSession, hunt_id: int, vacancy_ids: list[int]) -> None:
    if not vacancy_ids:
        return
    have = set(
        (
            await session.execute(
                select(HuntPin.vacancy_id).where(HuntPin.hunt_id == hunt_id, HuntPin.vacancy_id.in_(vacancy_ids))
            )
        )
        .scalars()
        .all()
    )
    for vacancy_id in vacancy_ids:
        if vacancy_id not in have:
            session.add(HuntPin(hunt_id=hunt_id, vacancy_id=vacancy_id))


async def set_pins(session: AsyncSession, user: User, vacancy: Vacancy, hunt_ids: list[int]) -> None:
    wanted = []
    seen: set[int] = set()
    for hunt_id in hunt_ids:
        if hunt_id in seen:
            continue
        await hunt_for_user(session, user, hunt_id)
        seen.add(hunt_id)
        wanted.append(hunt_id)
    current = list(
        (await session.execute(select(HuntPin).where(HuntPin.vacancy_id == vacancy.id))).scalars().all()
    )
    keep = set(wanted)
    for row in current:
        if row.hunt_id not in keep:
            await session.delete(row)
    have = {row.hunt_id for row in current}
    for hunt_id in wanted:
        if hunt_id not in have:
            session.add(HuntPin(hunt_id=hunt_id, vacancy_id=vacancy.id))
    await session.flush()


async def hunts_for_vacancy(session: AsyncSession, user: User, vacancy: Vacancy) -> list[dict]:
    theses = await list_hunts(session, user)
    pinned = set(
        (await session.execute(select(HuntPin.hunt_id).where(HuntPin.vacancy_id == vacancy.id))).scalars().all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "pinned": row.id in pinned,
            "matched": vacancy_matches(row, vacancy),
        }
        for row in theses
    ]


def hunt_field_defs(thesis: HuntThesis | None, profile: UserProfile | None) -> list[dict]:
    if thesis is not None:
        fields = normalize_defs(thesis.custom_fields, strict=False)
        if fields:
            return fields
    if profile is not None:
        return normalize_defs(profile.custom_fields, strict=False)
    return []


async def fields_for_vacancy(
    session: AsyncSession,
    user: User,
    vacancy: Vacancy,
    *,
    hunt: HuntThesis | None,
    profile: UserProfile,
) -> list[dict]:
    if hunt is not None:
        return hunt_field_defs(hunt, profile)
    refs = await hunts_for_vacancy(session, user, vacancy)
    member_ids = {item["id"] for item in refs if item["pinned"] or item["matched"]}
    if not member_ids:
        return hunt_field_defs(None, profile)
    theses = await list_hunts(session, user)
    groups = [normalize_defs(row.custom_fields, strict=False) for row in theses if row.id in member_ids]
    return concat_defs(groups) or hunt_field_defs(None, profile)


async def save_hunt_fields(session: AsyncSession, thesis: HuntThesis, raw: object) -> list[dict]:
    thesis.custom_fields = normalize_defs(raw)
    flag_modified(thesis, "custom_fields")
    await session.flush()
    return list(thesis.custom_fields)


async def seed_fields_on_create(session: AsyncSession, user: User, thesis: HuntThesis, profile: UserProfile) -> None:
    others = (
        await session.execute(
            select(func.count(HuntThesis.id)).where(HuntThesis.user_id == user.id, HuntThesis.id != thesis.id)
        )
    ).scalar_one()
    if int(others or 0) > 0:
        return
    inherited = normalize_defs(profile.custom_fields, strict=False)
    if inherited:
        thesis.custom_fields = inherited
        flag_modified(thesis, "custom_fields")
