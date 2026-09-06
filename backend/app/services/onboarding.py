from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donor_cache import DonorListing
from app.models.hunt_thesis import HuntThesis
from app.models.user import User
from app.models.vacancy import PipelineStage, Vacancy
from app.services.auth import ensure_profile
from app.services.resume import resume_for_llm
from app.services.hunts import list_hunts, seed_fields_on_create
from app.services.scraper.engine import upsert_vacancy
from app.services.scraper.sources.it_job_gate import listing_is_it_job
from app.services.scraper.sources.stack_lexicon import matching_stack_ids
from app.services.thesis import refresh_user_theses

SEED_N = 3


def hunt_name_from_resume(text: str, stacks: list[str]) -> str:
    if stacks:
        label = stacks[0].replace("_", " ").replace("-", " ").strip()
        return (label[:1].upper() + label[1:])[:48] if label else "Направление"
    for line in (text or "").splitlines():
        bit = line.strip()
        if 8 <= len(bit) <= 80:
            return bit[:48]
    return "Направление"


async def inbox_count_for(session: AsyncSession, user_id: int) -> int:
    return int(
        (
            await session.execute(
                select(func.count(Vacancy.id)).where(
                    Vacancy.user_id == user_id,
                    Vacancy.pipeline_stage != PipelineStage.TRASH,
                )
            )
        ).scalar()
        or 0
    )


async def onboarding_status(session: AsyncSession, user: User) -> dict:
    profile = await ensure_profile(session, user)
    cards = await inbox_count_for(session, user.id)
    resume = bool(resume_for_llm(profile))
    return {
        "has_resume": resume,
        "inbox_count": cards,
        "needed": (not resume) and cards < SEED_N,
    }


async def ensure_direction(session: AsyncSession, user: User, resume: str, stacks: list[str]) -> HuntThesis | None:
    hunts = await list_hunts(session, user)
    if hunts:
        return hunts[0]
    row = HuntThesis(
        user_id=user.id,
        name=hunt_name_from_resume(resume, stacks),
        role_query=" ".join(stacks[:6]),
        enabled=True,
    )
    session.add(row)
    await session.flush()
    profile = await ensure_profile(session, user)
    await seed_fields_on_create(session, user, row, profile)
    if profile.active_hunt_id is None:
        profile.active_hunt_id = row.id
    return row


async def seed_from_resume(session: AsyncSession, user: User, *, limit: int = SEED_N) -> dict:
    profile = await ensure_profile(session, user)
    resume = resume_for_llm(profile)
    stacks = matching_stack_ids(resume)[:10]
    cards = await inbox_count_for(session, user.id)
    hunt = await ensure_direction(session, user, resume, stacks)
    need = max(0, limit - cards)
    seeded = 0
    if need:
        rows = (
            await session.execute(select(DonorListing).order_by(DonorListing.id.desc()).limit(500))
        ).scalars().all()
        ranked: list[tuple[int, DonorListing]] = []
        stack_set = set(stacks)
        for row in rows:
            payload = dict(row.payload or {})
            payload.setdefault("source", row.source)
            payload.setdefault("source_id", row.source_id)
            if not listing_is_it_job(payload):
                continue
            blob = " ".join(
                [
                    str(payload.get("title") or ""),
                    str(payload.get("company") or ""),
                    " ".join(str(item) for item in (payload.get("skills") or [])),
                ]
            )
            overlap = len(set(matching_stack_ids(blob)) & stack_set) if stack_set else 1
            if stack_set and overlap == 0:
                continue
            ranked.append((overlap, row))
        ranked.sort(key=lambda item: -item[0])
        seen: set[tuple[str, str]] = set()
        for _score, row in ranked:
            key = (row.source, row.source_id)
            if key in seen:
                continue
            seen.add(key)
            payload = dict(row.payload or {})
            payload.setdefault("source", row.source)
            payload.setdefault("source_id", row.source_id)
            _, kind = await upsert_vacancy(session, payload, scraper_config_id=None, user_id=user.id)
            if kind == "new":
                seeded += 1
            if seeded >= need:
                break
        await refresh_user_theses(session, user.id, commit=False)
    await session.commit()
    return {
        "has_resume": bool(resume),
        "seeded": seeded,
        "inbox_count": cards + seeded,
        "hunt_id": hunt.id if hunt else None,
        "stacks": stacks[:6],
        "needed": False,
    }
