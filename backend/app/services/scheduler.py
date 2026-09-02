from __future__ import annotations

from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.metrics import (
    scheduler_jobs,
    scheduler_running,
    scraper_run_seconds,
    scraper_runs_total,
    telegram_parse_total,
    vacancies_scored_total,
)
from app.models.host_telegram import HostTelegram
from app.models.scraper_config import ScraperConfig
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.scraper.engine import run_config
from app.services.scoring.scorer import score_pending
from app.services.telegram_parse import parse_all_channels
from app.services.google_calendar import mark_pulled, pull_hunt_events

scheduler = AsyncIOScheduler(
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120},
)


def _redis_jobstore():
    from apscheduler.jobstores.redis import RedisJobStore

    parsed = urlparse(settings.redis_url)
    db = (parsed.path or "/0").lstrip("/") or "0"
    return RedisJobStore(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 6379,
        db=int(db),
        password=parsed.password,
    )


async def _job(config_id: int) -> None:
    async with SessionLocal() as session:
        config = await session.get(ScraperConfig, config_id)
        if not config or not config.enabled or not config.user_id:
            return
        try:
            with scraper_run_seconds.time():
                run = await run_config(session, config)
            scraper_runs_total.labels(status=run.status or "unknown").inc()
        except Exception:
            scraper_runs_total.labels(status="error").inc()
        try:
            scored = await score_pending(session, user_id=config.user_id, limit=15)
            vacancies_scored_total.inc(len(scored))
        except Exception:
            await session.rollback()


async def _telegram_job() -> None:
    async with SessionLocal() as session:
        host = await session.get(HostTelegram, 1)
        if host is None or host.status != "connected":
            return
        try:
            run = await parse_all_channels(session)
            telegram_parse_total.labels(status=run.status or "unknown").inc()
        except Exception:
            telegram_parse_total.labels(status="error").inc()
            return
        users = (await session.execute(select(User.id))).scalars().all()
        for uid in users:
            try:
                scored = await score_pending(session, user_id=uid, limit=8)
                vacancies_scored_total.inc(len(scored))
            except Exception:
                await session.rollback()


async def _google_pull_job() -> None:
    async with SessionLocal() as session:
        profiles = (
            await session.execute(
                select(UserProfile).where(UserProfile.google_refresh_token.isnot(None))
            )
        ).scalars().all()
        for profile in profiles:
            if not profile.user_id:
                continue
            user = await session.get(User, profile.user_id)
            if user is None:
                continue
            try:
                await pull_hunt_events(session, user, profile)
                profile.google_pulled_at = mark_pulled(user.id)
                await session.commit()
            except Exception:
                await session.rollback()


async def sync_jobs() -> None:
    if not scheduler.running:
        return
    async with SessionLocal() as session:
        result = await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
        configs = result.scalars().all()

    existing = {job.id for job in scheduler.get_jobs()}
    wanted = {f"scraper-{c.id}" for c in configs}
    wanted.add("telegram-channels")
    wanted.add("google-hunt-pull")
    wanted.add("resync-jobs")

    for job_id in existing - wanted:
        scheduler.remove_job(job_id)

    for config in configs:
        job_id = f"scraper-{config.id}"
        minutes = max(5, config.interval_minutes or 60)
        scheduler.add_job(
            _job,
            "interval",
            minutes=minutes,
            id=job_id,
            args=[config.id],
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    scheduler.add_job(
        _telegram_job,
        "interval",
        minutes=max(10, settings.telegram_parse_interval_minutes),
        id="telegram-channels",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _google_pull_job,
        "interval",
        minutes=5,
        id="google-hunt-pull",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        sync_jobs,
        "interval",
        minutes=1,
        id="resync-jobs",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler_jobs.set(len(scheduler.get_jobs()))


def bind_jobstore() -> None:
    """Point the default store at Redis so the API can read next_run without running jobs."""
    if not settings.redis_url:
        return
    from apscheduler.jobstores.redis import RedisJobStore

    current = scheduler._jobstores.get("default")
    if isinstance(current, RedisJobStore):
        return
    import redis

    redis.from_url(settings.redis_url).ping()
    store = _redis_jobstore()
    if "default" in scheduler._jobstores:
        scheduler.remove_jobstore("default")
    scheduler.add_jobstore(store, "default")


def start_scheduler() -> None:
    if scheduler.running:
        return
    bind_jobstore()
    scheduler.start()
    scheduler_running.set(1)
