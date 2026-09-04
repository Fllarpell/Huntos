from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.metrics import (
    scheduler_jobs,
    scheduler_running,
    scrape_queue_depth,
    scraper_run_seconds,
    scraper_runs_total,
    telegram_parse_total,
    vacancies_scored_total,
)
from app.models.host_telegram import HostTelegram
from app.models.scrape_queue import ScrapeQueueItem
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.scraper.queue import drain_queue, enqueue_due_queries, fail_open_queue
from app.services.scoring.scorer import score_pending
from app.services.telegram_bot import poll_updates, tick as telegram_bot_tick
from app.services.telegram_parse import parse_all_channels
from app.services.google_calendar import mark_pulled, pull_hunt_events
from app.services.hackathons_sync import refresh_hackathons
from app.services.internship_monitor import refresh_internship_statuses

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


async def _scrape_tick() -> None:
    """One host crawler. Unique queries wait in scrape_queue; a few origins run together."""
    async with SessionLocal() as session:
        await fail_open_queue(
            session,
            reason="прерван (парсер завис или сервер перезапустился)",
            older_than=timedelta(minutes=20),
        )
        pending = (
            await session.execute(
                select(func.count()).select_from(ScrapeQueueItem).where(
                    ScrapeQueueItem.status.in_(("pending", "running"))
                )
            )
        ).scalar_one()
        scrape_queue_depth.set(int(pending or 0))
        try:
            await enqueue_due_queries(session)
            with scraper_run_seconds.time():
                results = await drain_queue(session)
            for result in results:
                scraper_runs_total.labels(status=result.status or "unknown").inc()
                for uid in dict.fromkeys(result.user_ids):
                    try:
                        scored = await score_pending(session, user_id=uid, limit=15)
                        vacancies_scored_total.inc(len(scored))
                    except Exception:
                        await session.rollback()
        except Exception:
            scraper_runs_total.labels(status="error").inc()


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


async def run_internship_monitor_job() -> None:
    async with SessionLocal() as session:
        try:
            await refresh_internship_statuses(session)
        except Exception:
            await session.rollback()


async def run_hackathon_sync_job() -> None:
    async with SessionLocal() as session:
        try:
            await refresh_hackathons(session)
        except Exception:
            await session.rollback()


async def _telegram_bot_job() -> None:
    async with SessionLocal() as session:
        try:
            await poll_updates(session)
            await telegram_bot_tick(session)
        except Exception:
            await session.rollback()


async def run_salary_market_job() -> None:
    from app.services.salary_market import refresh_salary_benchmarks

    try:
        await refresh_salary_benchmarks()
    except Exception:
        pass


async def sync_jobs() -> None:
    if not scheduler.running:
        return

    existing = {job.id for job in scheduler.get_jobs()}
    wanted = {
        "scrape-tick",
        "telegram-channels",
        "google-hunt-pull",
        "internship-monitor",
        "hackathon-sync",
        "salary-market",
        "telegram-bot",
        "resync-jobs",
    }

    for job_id in existing - wanted:
        scheduler.remove_job(job_id)

    scheduler.add_job(
        _scrape_tick,
        "interval",
        minutes=1,
        id="scrape-tick",
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
        run_internship_monitor_job,
        "cron",
        hour=6,
        minute=0,
        id="internship-monitor",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_hackathon_sync_job,
        "cron",
        hour=6,
        minute=20,
        id="hackathon-sync",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _telegram_bot_job,
        "interval",
        seconds=30,
        id="telegram-bot",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_salary_market_job,
        "cron",
        hour=6,
        minute=40,
        id="salary-market",
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
