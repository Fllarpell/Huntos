from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.donor_cache import DonorQueryCache
from app.models.scrape_queue import ScrapeQueueItem
from app.models.scraper_config import ScraperConfig
from app.models.scraper_run import ScraperRun
from app.models.user import User
from app.services.scraper.engine import (
    deliver_from_pool,
    fanout_listings,
    query_key_for,
    refresh_query_cache,
)
from app.services.scraper.gate import gate_key, global_concurrency, source_concurrency
from app.services.scraper.query_key import crawl_label, make_query_key

log = logging.getLogger(__name__)

_OPEN = ("queued", "running")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class ProcessResult:
    query_key: str
    status: str
    user_ids: list[int]
    from_cache: bool


def clamp_interval(minutes: int | None) -> int:
    floor = max(1, settings.scraper_global_min_interval_minutes)
    value = int(minutes or 60)
    return max(floor, min(value, 24 * 60))


def ensure_config_key(config: ScraperConfig) -> str:
    key = make_query_key(config.source, config.query_params)
    config.query_key = key
    return key


def crawl_interval_minutes(configs: list[ScraperConfig]) -> int:
    floor = max(1, settings.scraper_global_min_interval_minutes)
    if not configs:
        return floor
    wanted = min(max(1, row.interval_minutes or 60) for row in configs)
    return max(floor, wanted)


def next_run_at_for(
    cache: DonorQueryCache | None,
    config: ScraperConfig,
    peers: list[ScraperConfig],
) -> datetime | None:
    if not config.enabled:
        return None
    interval = crawl_interval_minutes(peers or [config])
    if cache and cache.last_fetched_at:
        return cache.last_fetched_at + timedelta(minutes=interval)
    return _now()


def _config_ids(item: ScrapeQueueItem) -> list[int]:
    ids = [int(x) for x in (item.requested_config_ids or []) if x]
    if item.requested_by_config_id and item.requested_by_config_id not in ids:
        ids.append(item.requested_by_config_id)
    return ids


async def fail_open_queue(
    session: AsyncSession,
    *,
    reason: str,
    older_than: timedelta | None = None,
) -> int:
    stmt = select(ScrapeQueueItem).where(ScrapeQueueItem.status == "running")
    if older_than is not None:
        stmt = stmt.where(ScrapeQueueItem.started_at < _now() - older_than)
    rows = (await session.execute(stmt)).scalars().all()
    now = _now()
    keys: list[str] = []
    for item in rows:
        item.status = "error"
        item.error = reason
        item.finished_at = now
        keys.append(item.query_key)
    if keys:
        caches = (
            await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key.in_(set(keys))))
        ).scalars().all()
        for cache in caches:
            if cache.last_status == "running":
                cache.last_status = "error"
                cache.last_error = reason
    if rows:
        await session.commit()
    return len(rows)


async def enqueue_query(
    session: AsyncSession,
    *,
    config: ScraperConfig | None = None,
    query_key: str | None = None,
    source: str | None = None,
    force: bool = False,
) -> ScrapeQueueItem:
    key = query_key or (query_key_for(config) if config else None)
    src = source or (config.source if config else None)
    if not key or not src:
        raise ValueError("enqueue_query needs query_key and source")

    existing = (
        await session.execute(
            select(ScrapeQueueItem)
            .where(
                ScrapeQueueItem.query_key == key,
                ScrapeQueueItem.status.in_(("pending", "running")),
            )
            .order_by(ScrapeQueueItem.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if force:
            existing.force = True
        if config is not None:
            ids = _config_ids(existing)
            if config.id not in ids:
                ids.append(config.id)
                existing.requested_config_ids = ids
            existing.requested_by_config_id = existing.requested_by_config_id or config.id
            existing.requested_by_user_id = existing.requested_by_user_id or config.user_id
        await session.commit()
        return existing

    item = ScrapeQueueItem(
        query_key=key,
        source=src,
        status="pending",
        force=force,
        requested_by_config_id=config.id if config else None,
        requested_by_user_id=config.user_id if config else None,
        requested_config_ids=[config.id] if config else [],
        queued_at=_now(),
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def enqueue_due_queries(session: AsyncSession) -> int:
    configs = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    groups: dict[str, list[ScraperConfig]] = {}
    for row in configs:
        groups.setdefault(query_key_for(row), []).append(row)

    added = 0
    for key, rows in groups.items():
        sample = rows[0]
        cache = (
            await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key == key))
        ).scalar_one_or_none()
        interval = crawl_interval_minutes(rows)
        fetched = cache.last_fetched_at if cache else None
        due = fetched is None or (_now() - fetched).total_seconds() >= interval * 60
        if not due:
            continue
        before = (
            await session.execute(
                select(ScrapeQueueItem.id).where(
                    ScrapeQueueItem.query_key == key,
                    ScrapeQueueItem.status.in_(("pending", "running")),
                )
            )
        ).first()
        item = await enqueue_query(session, query_key=key, source=sample.source, force=False)
        if before is None and item.status == "pending":
            added += 1
    return added


async def ensure_queued_run(session: AsyncSession, config: ScraperConfig) -> ScraperRun:
    row = (
        await session.execute(
            select(ScraperRun)
            .where(
                ScraperRun.scraper_config_id == config.id,
                ScraperRun.status.in_(_OPEN),
            )
            .order_by(ScraperRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    run = ScraperRun(
        scraper_config_id=config.id,
        user_id=config.user_id,
        started_at=_now(),
        status="queued",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _open_run(session: AsyncSession, config: ScraperConfig) -> ScraperRun:
    row = (
        await session.execute(
            select(ScraperRun)
            .where(
                ScraperRun.scraper_config_id == config.id,
                ScraperRun.status.in_(_OPEN),
            )
            .order_by(ScraperRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None:
        row.status = "running"
        return row
    run = ScraperRun(
        scraper_config_id=config.id,
        user_id=config.user_id,
        started_at=_now(),
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


async def _finish_runs(
    session: AsyncSession,
    configs: list[ScraperConfig],
    stats: dict[int, tuple[int, int, int]],
    *,
    status: str,
    error: str | None,
) -> None:
    now = _now()
    for config in configs:
        run = await _open_run(session, config)
        found, new_count, updated_count = stats.get(config.id, (0, 0, 0))
        run.status = status
        run.error = error
        run.found_count = found
        run.new_count = new_count
        run.updated_count = updated_count
        run.finished_at = now
    await session.commit()


async def _subscribers(
    session: AsyncSession,
    query_key: str,
    extra_ids: list[int],
) -> list[ScraperConfig]:
    rows = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    extra = set(extra_ids)
    out: list[ScraperConfig] = []
    for row in rows:
        if query_key_for(row) != query_key:
            continue
        if row.enabled or row.id in extra:
            out.append(row)
    return out


async def _running_by_gate(session: AsyncSession) -> dict[str, list[int]]:
    rows = (
        await session.execute(
            select(ScrapeQueueItem.id, ScrapeQueueItem.source).where(ScrapeQueueItem.status == "running")
        )
    ).all()
    grouped: dict[str, list[int]] = {}
    for item_id, source in rows:
        grouped.setdefault(gate_key(source), []).append(int(item_id))
    for ids in grouped.values():
        ids.sort()
    return grouped


async def claim_next(session: AsyncSession) -> ScrapeQueueItem | None:
    pending = (
        await session.execute(
            select(ScrapeQueueItem).where(ScrapeQueueItem.status == "pending").order_by(ScrapeQueueItem.id)
        )
    ).scalars().all()
    if not pending:
        return None
    keys = list({row.query_key for row in pending})
    configs = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    counts: dict[str, int] = {key: 0 for key in keys}
    for row in configs:
        key = query_key_for(row)
        if key in counts:
            counts[key] += 1
    pending.sort(key=lambda row: (-counts.get(row.query_key, 0), row.id))

    for candidate in pending:
        key = gate_key(candidate.source)
        running = await _running_by_gate(session)
        if len(running.get(key, [])) >= source_concurrency(candidate.source):
            continue
        result = await session.execute(
            update(ScrapeQueueItem)
            .where(ScrapeQueueItem.id == candidate.id, ScrapeQueueItem.status == "pending")
            .values(status="running", started_at=_now())
        )
        await session.commit()
        if result.rowcount == 0:
            continue
        running = await _running_by_gate(session)
        keep = set(running.get(key, [])[: source_concurrency(candidate.source)])
        claimed = await session.get(ScrapeQueueItem, candidate.id)
        if claimed is None:
            return None
        if claimed.id not in keep:
            claimed.status = "pending"
            claimed.started_at = None
            await session.commit()
            continue
        return claimed
    return None


async def process_one(
    session: AsyncSession,
    *,
    item: ScrapeQueueItem | None = None,
) -> ProcessResult | None:
    claimed = item
    if claimed is None:
        claimed = await claim_next(session)
    elif claimed.status == "pending":
        claimed.status = "running"
        claimed.started_at = _now()
        await session.commit()
    if claimed is None:
        return None

    extra_ids = _config_ids(claimed)
    item_id = claimed.id
    query_key = claimed.query_key
    configs = await _subscribers(session, query_key, extra_ids)
    if not configs:
        claimed.status = "done"
        claimed.finished_at = _now()
        await session.commit()
        return ProcessResult(query_key, "ok", [], True)

    sample = configs[0]
    try:
        if not claimed.force:
            stats: dict[int, tuple[int, int, int]] = {}
            missing = False
            for config in configs:
                if not config.user_id:
                    continue
                got = await deliver_from_pool(session, config)
                if got is None:
                    missing = True
                    break
                stats[config.id] = got
            cache = (
                await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key == query_key))
            ).scalar_one_or_none()
            ttl = max(settings.scraper_cache_ttl_minutes, settings.scraper_global_min_interval_minutes, 5)
            fresh = (
                cache is not None
                and cache.last_status == "ok"
                and cache.last_fetched_at is not None
                and (_now() - cache.last_fetched_at).total_seconds() < ttl * 60
            )
            if not missing and fresh:
                await _finish_runs(session, configs, stats, status="ok", error=None)
                claimed = await session.get(ScrapeQueueItem, item_id)
                if claimed is not None:
                    claimed.status = "done"
                    claimed.finished_at = _now()
                    await session.commit()
                return ProcessResult(
                    query_key,
                    "ok",
                    [row.user_id for row in configs if row.user_id],
                    True,
                )

        cache, listings, from_cache = await refresh_query_cache(
            session, sample, force=claimed.force
        )
        claimed = await session.get(ScrapeQueueItem, item_id)
        extra_ids = _config_ids(claimed) if claimed else extra_ids
        configs = await _subscribers(session, query_key, extra_ids)
        stats: dict[int, tuple[int, int, int]] = {}
        for config in configs:
            if not config.user_id:
                continue
            stats[config.id] = await fanout_listings(
                session,
                listings,
                user_id=config.user_id,
                scraper_config_id=config.id,
                source=config.source,
                query_params=config.query_params,
            )
        error = cache.last_error if cache.last_status == "error" else None
        status = "error" if cache.last_status == "error" and not listings else "ok"
        await _finish_runs(session, configs, stats, status=status, error=error)
        claimed.status = "done" if status == "ok" else "error"
        claimed.error = error
        claimed.finished_at = _now()
        await session.commit()
        return ProcessResult(
            query_key,
            status,
            [row.user_id for row in configs if row.user_id],
            from_cache,
        )
    except Exception as exc:  # noqa: BLE001 — persist the queue item
        log.exception("scrape queue failed key=%s", query_key)
        error = str(exc)[:2000]
        await session.rollback()
        claimed = await session.get(ScrapeQueueItem, item_id)
        if claimed is not None:
            claimed.status = "error"
            claimed.error = error
            claimed.finished_at = _now()
        configs = await _subscribers(session, query_key, extra_ids)
        await _finish_runs(session, configs, {}, status="error", error=error)
        return ProcessResult(query_key, "error", [row.user_id for row in configs if row.user_id], False)


async def process_query_key(session: AsyncSession, query_key: str) -> ProcessResult | None:
    item = (
        await session.execute(
            select(ScrapeQueueItem)
            .where(
                ScrapeQueueItem.query_key == query_key,
                ScrapeQueueItem.status == "pending",
            )
            .order_by(ScrapeQueueItem.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if item is None:
        return None
    return await process_one(session, item=item)


def _use_parallel_drain() -> bool:
    return (not settings.is_sqlite()) and global_concurrency() > 1


async def drain_queue(session: AsyncSession, *, limit: int = 50) -> list[ProcessResult]:
    if not _use_parallel_drain():
        results: list[ProcessResult] = []
        for _ in range(limit):
            result = await process_one(session)
            if result is None:
                break
            results.append(result)
        return results
    return await _drain_parallel(limit)


async def _drain_parallel(limit: int) -> list[ProcessResult]:
    from app.db import SessionLocal

    cap = global_concurrency()
    results: list[ProcessResult] = []
    lock = asyncio.Lock()
    remaining = limit
    stop = False

    async def worker() -> None:
        nonlocal remaining, stop
        while True:
            async with lock:
                if stop or remaining <= 0:
                    return
                remaining -= 1
            async with SessionLocal() as own:
                result = await process_one(own)
            if result is None:
                async with lock:
                    stop = True
                return
            async with lock:
                results.append(result)

    await asyncio.gather(*(worker() for _ in range(cap)))
    return results


async def backfill_query_keys(session: AsyncSession) -> int:
    rows = (await session.execute(select(ScraperConfig))).scalars().all()
    changed = 0
    for row in rows:
        key = make_query_key(row.source, row.query_params)
        if row.query_key != key:
            row.query_key = key
            changed += 1
    if changed:
        await session.commit()
    return changed


@dataclass
class HostCrawl:
    query_key: str
    source: str
    name: str
    listing_url: str | None
    query_params: dict
    last_fetched_at: datetime | None
    last_status: str
    last_error: str | None
    found_count: int
    queue_status: str | None
    subscriber_count: int
    subscribers: list[str]
    host_subscribed: bool


async def list_host_crawls(
    session: AsyncSession,
    *,
    viewer_id: int,
    reveal_emails: bool = False,
) -> list[HostCrawl]:
    """Shared crawl pool. Same filters = one donor trip; more subscribers = warmer cache."""
    configs = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    groups: dict[str, list[ScraperConfig]] = {}
    for row in configs:
        groups.setdefault(query_key_for(row), []).append(row)
    if not groups:
        return []

    caches = {
        row.query_key: row
        for row in (
            await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key.in_(list(groups))))
        ).scalars().all()
    }
    queued = {
        row.query_key: row.status
        for row in (
            await session.execute(
                select(ScrapeQueueItem).where(
                    ScrapeQueueItem.query_key.in_(list(groups)),
                    ScrapeQueueItem.status.in_(("pending", "running")),
                )
            )
        ).scalars().all()
    }
    user_ids = {row.user_id for rows in groups.values() for row in rows if row.user_id}
    emails = {
        row.id: row.email
        for row in (
            await session.execute(select(User).where(User.id.in_(list(user_ids))))
        ).scalars().all()
    }

    out: list[HostCrawl] = []
    for key, rows in groups.items():
        sample = rows[0]
        cache = caches.get(key)
        names = [emails.get(row.user_id, f"id:{row.user_id}") for row in rows if row.user_id]
        unique_names = list(dict.fromkeys(names))
        out.append(
            HostCrawl(
                query_key=key,
                source=sample.source,
                name=sample.name or crawl_label(sample.source, sample.query_params),
                listing_url=(cache.listing_url if cache else None) or sample.listing_url,
                query_params=dict((cache.query_params if cache else None) or sample.query_params or {}),
                last_fetched_at=cache.last_fetched_at if cache else None,
                last_status=cache.last_status if cache else "idle",
                last_error=cache.last_error if cache else None,
                found_count=cache.found_count if cache else 0,
                queue_status=queued.get(key),
                subscriber_count=len(rows),
                subscribers=unique_names if reveal_emails else [],
                host_subscribed=any(row.user_id == viewer_id for row in rows),
            )
        )
    out.sort(
        key=lambda row: (
            -row.subscriber_count,
            0 if row.queue_status == "running" else 1 if row.queue_status == "pending" else 2,
            0 if row.last_fetched_at is None else 1,
            row.name.lower(),
        )
    )
    return out
