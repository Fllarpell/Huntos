from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.models.scraper_config import ScraperConfig
from app.models.scraper_run import ScraperRun
from app.models.user import User
from app.schemas.dto import ScraperConfigIn, ScraperConfigOut, ScraperRunOut
from app.services.deps import config_for_user, get_scope_user
from app.services.scheduler import scheduler, sync_jobs
from app.services.scraper.engine import fail_open_runs, run_config
from app.services.scraper.sources.hh_filters import auto_name as hh_auto_name
from app.services.scraper.sources.hh_filters import listing_url_from_params as hh_listing_url
from app.services.scraper.sources.hh_filters import normalize_hh_params
from app.services.scraper.sources.hirehi import listing_url_from_params, parse_listing_url
from app.services.scraper.sources.hirehi_filters import auto_name, normalize_hirehi_params
from app.services.scoring.scorer import score_pending

router = APIRouter(prefix="/api", tags=["scraper"])


def _config_fields(payload: ScraperConfigIn) -> dict:
    source = (payload.source or "hirehi").strip() or "hirehi"
    if source == "hh":
        params = normalize_hh_params(payload.query_params)
        name = (payload.name or "").strip() or hh_auto_name(params)
        listing = hh_listing_url(params)
    else:
        source = "hirehi"
        params = dict(payload.query_params or {})
        has_filters = any(
            params.get(key)
            for key in ("search", "format", "level", "subcategory", "category", "english", "direct_contact")
        )
        if not has_filters and payload.listing_url:
            params = parse_listing_url(payload.listing_url)
        params = normalize_hirehi_params(params)
        name = (payload.name or "").strip() or auto_name(params)
        listing = listing_url_from_params(params)
    return {
        "name": name,
        "source": source,
        "enabled": payload.enabled,
        "query_params": params,
        "listing_url": listing,
        "interval_minutes": payload.interval_minutes,
        "max_pages": payload.max_pages,
    }


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def _config_out(row: ScraperConfig, last_run: ScraperRun | None = None) -> ScraperConfigOut:
    job = scheduler.get_job(f"scraper-{row.id}") if row.enabled else None
    next_run = _naive(getattr(job, "next_run_time", None)) if job else None
    return ScraperConfigOut(
        **ScraperConfigOut.model_validate(row).model_dump(exclude={"last_run", "next_run_at"}),
        last_run=ScraperRunOut.model_validate(last_run) if last_run else None,
        next_run_at=next_run,
    )


async def _latest_runs(session: AsyncSession, user_id: int) -> dict[int, ScraperRun]:
    rows = (
        await session.execute(
            select(ScraperRun)
            .where(ScraperRun.user_id == user_id)
            .order_by(ScraperRun.id.desc())
            .limit(80)
        )
    ).scalars().all()
    latest: dict[int, ScraperRun] = {}
    for run in rows:
        if run.scraper_config_id and run.scraper_config_id not in latest:
            latest[run.scraper_config_id] = run
    return latest


@router.get("/scraper-configs", response_model=list[ScraperConfigOut])
async def list_configs(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> list[ScraperConfigOut]:
    await fail_open_runs(
        session,
        reason="прерван (парсер завис или сервер перезапустился)",
        older_than=timedelta(minutes=20),
        user_id=user.id,
    )
    rows = (
        await session.execute(
            select(ScraperConfig).where(ScraperConfig.user_id == user.id).order_by(ScraperConfig.id)
        )
    ).scalars().all()
    latest = await _latest_runs(session, user.id)
    return [_config_out(row, latest.get(row.id)) for row in rows]


@router.post("/scraper-configs", response_model=ScraperConfigOut)
async def create_config(
    payload: ScraperConfigIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ScraperConfigOut:
    config = ScraperConfig(user_id=user.id, **_config_fields(payload))
    session.add(config)
    await session.commit()
    await session.refresh(config)
    await sync_jobs()
    return _config_out(config)


@router.put("/scraper-configs/{config_id}", response_model=ScraperConfigOut)
async def update_config(
    config_id: int,
    payload: ScraperConfigIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ScraperConfigOut:
    config = await config_for_user(session, user, config_id)
    for key, value in _config_fields(payload).items():
        setattr(config, key, value)
    await session.commit()
    await session.refresh(config)
    await sync_jobs()
    latest = await _latest_runs(session, user.id)
    return _config_out(config, latest.get(config.id))


@router.delete("/scraper-configs/{config_id}")
async def delete_config(
    config_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    config = await config_for_user(session, user, config_id)
    await session.delete(config)
    await session.commit()
    await sync_jobs()
    return {"ok": True}


@router.get("/scraper/runs", response_model=list[ScraperRunOut])
async def list_runs(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> list[ScraperRunOut]:
    rows = (
        await session.execute(
            select(ScraperRun)
            .where(ScraperRun.user_id == user.id)
            .order_by(ScraperRun.id.desc())
            .limit(20)
        )
    ).scalars().all()
    return [ScraperRunOut.model_validate(row) for row in rows]


async def _run_and_score(config_id: int, user_id: int) -> None:
    async with SessionLocal() as session:
        config = await session.get(ScraperConfig, config_id)
        if not config or config.user_id != user_id:
            return
        try:
            await run_config(session, config)
        except Exception:
            return
        try:
            await score_pending(session, user_id=user_id, limit=15)
        except Exception:
            await session.rollback()


@router.post("/scraper/run/{config_id}")
async def run_now(
    config_id: int,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    await config_for_user(session, user, config_id)
    background.add_task(_run_and_score, config_id, user.id)
    return {"ok": True, "status": "started"}


@router.post("/scraper/score-pending")
async def score_now(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    rows = await score_pending(session, user_id=user.id, limit=15)
    return {"scored": len(rows)}
