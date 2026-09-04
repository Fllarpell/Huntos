"""Dedicated process for APScheduler + Telethon. API sets APP_ROLE=api."""

from __future__ import annotations

import asyncio
import logging
import os

from app.config import settings
from app.db_migrate import apply_schema
from app.metrics import scheduler_running
from app.models import (  # noqa: F401
    AuthSession,
    HostTelegram,
    HuntPin,
    HuntThesis,
    OutreachWave,
    PingSlot,
    SavedContact,
    DonorListing,
    DonorQueryCache,
    ScrapeQueueItem,
    ScraperConfig,
    ScraperRun,
    TelegramChannel,
    TelegramParseRun,
    TelegramPost,
    TelegramBotBind,
    User,
    UserProfile,
    Vacancy,
    VacancyEvent,
)
from app.observability import setup_tracing
from app.services.scheduler import (
    run_hackathon_sync_job,
    run_internship_monitor_job,
    run_salary_market_job,
    start_scheduler,
    sync_jobs,
)

log = logging.getLogger("worker")


def _serve_metrics() -> None:
    port = int(os.environ.get("WF_METRICS_PORT", "9101"))
    from prometheus_client import start_http_server

    start_http_server(port, addr="0.0.0.0")
    log.info("worker metrics on 0.0.0.0:%s", port)


async def _run() -> None:
    setup_tracing()
    if settings.is_sqlite():
        await apply_schema()
    _serve_metrics()
    start_scheduler()
    await sync_jobs()
    asyncio.create_task(run_internship_monitor_job())
    asyncio.create_task(run_hackathon_sync_job())
    asyncio.create_task(run_salary_market_job())
    scheduler_running.set(1)
    log.info("worker scheduler running role=%s redis=%s", settings.app_role, bool(settings.redis_url))
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
