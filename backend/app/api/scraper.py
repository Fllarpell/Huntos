from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal, get_session
from app.models.donor_cache import DonorQueryCache
from app.models.scrape_queue import ScrapeQueueItem
from app.models.scraper_config import ScraperConfig
from app.models.scraper_run import ScraperRun
from app.models.user import User
from app.models.vacancy import Vacancy
from app.schemas.dto import CareerBoardOut, DonorCrawlOut, ScraperConfigIn, ScraperConfigOut, ScraperRunOut
from app.services.deps import config_for_user, get_current_user, get_scope_user, require_host
from app.services.scheduler import sync_jobs
from app.services.scraper.engine import fail_open_runs, query_key_for, run_config
from app.services.scraper.query_key import make_query_key
from app.services.scraper.queue import clamp_interval, list_host_crawls, next_run_at_for
from app.services.scraper.registry import get_spec
from app.services.scraper.sources.career_catalog import BOARDS, board_public
from app.services.scraper.sources.hirehi import parse_listing_url
from app.services.scoring.scorer import score_pending

router = APIRouter(prefix="/api", tags=["scraper"])


def _config_fields(payload: ScraperConfigIn) -> dict:
    source = (payload.source or "hirehi").strip() or "hirehi"
    spec = get_spec(source)
    if spec is None:
        raise HTTPException(400, f"Неизвестный источник: {source}")
    params = dict(payload.query_params or {})
    if source == "hirehi":
        has_filters = any(
            params.get(key)
            for key in ("search", "format", "level", "subcategory", "category", "english", "direct_contact")
        )
        if not has_filters and payload.listing_url:
            params = parse_listing_url(payload.listing_url)
    params = spec.normalize_params(params)
    if source == "career" and not params.get("company"):
        raise HTTPException(400, "Выбери компанию")
    name = spec.auto_name(params)
    listing = spec.listing_url(params)
    interval = clamp_interval(payload.interval_minutes)
    return {
        "name": name,
        "source": source,
        "enabled": payload.enabled,
        "query_params": params,
        "listing_url": listing,
        "query_key": make_query_key(source, params),
        "interval_minutes": interval,
        "max_pages": payload.max_pages,
    }


def _config_out(
    row: ScraperConfig,
    last_run: ScraperRun | None = None,
    cache: DonorQueryCache | None = None,
    peers: list[ScraperConfig] | None = None,
) -> ScraperConfigOut:
    next_run = next_run_at_for(cache, row, peers or [row])
    return ScraperConfigOut(
        **ScraperConfigOut.model_validate(row).model_dump(exclude={"last_run", "next_run_at", "from_pool"}),
        last_run=ScraperRunOut.model_validate(last_run) if last_run else None,
        next_run_at=next_run,
        from_pool=bool(cache and cache.last_fetched_at and cache.last_status == "ok"),
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
    keys = [query_key_for(row) for row in rows]
    caches: dict[str, DonorQueryCache] = {}
    if keys:
        for cache in (
            await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key.in_(keys)))
        ).scalars().all():
            caches[cache.query_key] = cache
    all_enabled = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    peers_by_key: dict[str, list[ScraperConfig]] = {}
    for item in all_enabled:
        peers_by_key.setdefault(query_key_for(item), []).append(item)
    return [_config_out(row, latest.get(row.id), caches.get(query_key_for(row)), peers_by_key.get(query_key_for(row), [row])) for row in rows]


async def _enabled_count(session: AsyncSession, user_id: int, *, except_id: int | None = None) -> int:
    stmt = select(func.count()).select_from(ScraperConfig).where(
        ScraperConfig.user_id == user_id,
        ScraperConfig.enabled.is_(True),
    )
    if except_id is not None:
        stmt = stmt.where(ScraperConfig.id != except_id)
    return int((await session.execute(stmt)).scalar_one() or 0)


def _at_cap(enabled: int) -> bool:
    cap = settings.scraper_max_configs_per_user
    return cap > 0 and enabled >= cap


def _cap_error() -> HTTPException:
    cap = settings.scraper_max_configs_per_user
    return HTTPException(
        400,
        f"Слишком много активных поисков ({cap}). Очередь и так качает по одному — выключи ненужные.",
    )


async def _kick_saved_search(
    background: BackgroundTasks,
    session: AsyncSession,
    config: ScraperConfig,
    *,
    force: bool = False,
) -> ScraperRun | None:
    """Queue a host crawl. Cache miss → the machine fetches; hit → copy into this inbox."""
    if not config.enabled:
        return None
    run = await run_config(session, config, process=False, force=force)
    if settings.runs_scheduler() and config.user_id:
        background.add_task(_run_and_score, config.id, config.user_id, True, force)
    return run


@router.get("/scraper/boards", response_model=list[CareerBoardOut])
async def list_boards(user: User = Depends(get_current_user)) -> list[CareerBoardOut]:
    del user
    return [CareerBoardOut.model_validate(board_public(board)) for board in BOARDS]


@router.get("/scraper/crawls", response_model=list[DonorCrawlOut])
async def list_crawls(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_host),
) -> list[DonorCrawlOut]:
    rows = await list_host_crawls(
        session,
        viewer_id=user.id,
    )
    return [DonorCrawlOut.model_validate(row, from_attributes=True) for row in rows]


@router.post("/scraper-configs", response_model=ScraperConfigOut)
async def create_config(
    payload: ScraperConfigIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ScraperConfigOut:
    fields = _config_fields(payload)
    if fields["enabled"] and _at_cap(await _enabled_count(session, user.id)):
        raise _cap_error()
    config = ScraperConfig(user_id=user.id, **fields)
    session.add(config)
    await session.commit()
    await session.refresh(config)
    await sync_jobs()
    last_run = await _kick_saved_search(background, session, config)
    cache = (
        await session.execute(
            select(DonorQueryCache).where(DonorQueryCache.query_key == query_key_for(config))
        )
    ).scalar_one_or_none()
    return _config_out(config, last_run, cache)


@router.put("/scraper-configs/{config_id}", response_model=ScraperConfigOut)
async def update_config(
    config_id: int,
    payload: ScraperConfigIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ScraperConfigOut:
    config = await config_for_user(session, user, config_id)
    fields = _config_fields(payload)
    if fields["enabled"] and _at_cap(await _enabled_count(session, user.id, except_id=config.id)):
        raise _cap_error()
    for key, value in fields.items():
        setattr(config, key, value)
    await session.commit()
    await session.refresh(config)
    await sync_jobs()
    last_run = await _kick_saved_search(background, session, config, force=True)
    latest = await _latest_runs(session, user.id)
    cache = (
        await session.execute(
            select(DonorQueryCache).where(DonorQueryCache.query_key == query_key_for(config))
        )
    ).scalar_one_or_none()
    return _config_out(config, last_run or latest.get(config.id), cache)


@router.delete("/scraper-configs/{config_id}")
async def delete_config(
    config_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    config = await config_for_user(session, user, config_id)
    await session.execute(
        update(Vacancy).where(Vacancy.scraper_config_id == config.id).values(scraper_config_id=None)
    )
    await session.execute(
        update(ScraperRun).where(ScraperRun.scraper_config_id == config.id).values(scraper_config_id=None)
    )
    await session.execute(
        update(ScrapeQueueItem)
        .where(ScrapeQueueItem.requested_by_config_id == config.id)
        .values(requested_by_config_id=None)
    )
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


async def _run_and_score(config_id: int, user_id: int, process: bool = True, force: bool = False) -> None:
    async with SessionLocal() as session:
        config = await session.get(ScraperConfig, config_id)
        if not config or config.user_id != user_id:
            return
        try:
            await run_config(session, config, process=process, force=force)
        except Exception:
            return
        if not process:
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
    process = settings.runs_scheduler()
    background.add_task(_run_and_score, config_id, user.id, process=process, force=True)
    return {"ok": True, "status": "started" if process else "queued"}


@router.post("/scraper/score-pending")
async def score_now(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    rows = await score_pending(session, user_id=user.id, limit=15)
    return {"scored": len(rows)}
