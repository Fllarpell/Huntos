from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.contacts import router as contacts_router
from app.api.feedback import router as feedback_router
from app.api.chat import router as chat_router
from app.api.hackathons import router as hackathons_router
from app.api.internships import router as internships_router
from app.api.hunt import router as hunt_router
from app.api.auth import router as auth_router
from app.api.google import router as google_router
from app.api.telegram_bot import router as telegram_bot_router
from app.api.scraper import router as scraper_router
from app.api.settings import router as settings_router
from app.api.telegram import router as telegram_router
from app.api.vacancies import router as vacancies_router
from app.api.salary_market import router as salary_market_router
from app.db import SessionLocal, engine
from app.config import settings
from app.db_migrate import apply_schema
from app.observability import setup_tracing
from app.models import (  # noqa: F401
    AuthSession,
    HackathonEvent,
    HackathonTrack,
    InternshipMonitor,
    InternshipTrack,
    SavedContact,
    FeedbackNote,
    Conversation,
    ConversationMember,
    ChatMessage,
    TelegramBotBind,
    TelegramBotState,
    HuntPin,
    HuntThesis,
    OutreachWave,
    PingSlot,
    HostTelegram,
    DonorListing,
    DonorQueryCache,
    ScrapeQueueItem,
    ScraperConfig,
    ScraperRun,
    TelegramChannel,
    TelegramParseRun,
    TelegramPost,
    User,
    UserProfile,
    Vacancy,
    VacancyEvent,
    VacancySearch,
)
from app.services.scheduler import (
    bind_jobstore,
    run_hackathon_sync_job,
    run_internship_monitor_job,
    run_salary_market_job,
    start_scheduler,
    sync_jobs,
)
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from app.services.company_icon import backfill_company_icons
from app.services.scraper.engine import backfill_fingerprints, fail_open_runs, restore_overmerged_duplicates
from app.services.scraper.queue import backfill_query_keys, fail_open_queue
from app.services.telegram_parse import fail_open_telegram_runs
from app.services.scraper.sources.hirehi import backfill_job_page_urls
from app.services.seed import seed_defaults


@asynccontextmanager
async def lifespan(_: FastAPI):
    await apply_schema()
    async with SessionLocal() as session:
        await seed_defaults(session)
        await backfill_job_page_urls(session)
        await fail_open_runs(session, reason="прерван (сервер перезапустился)")
        await fail_open_queue(session, reason="прерван (сервер перезапустился)")
        await fail_open_telegram_runs(session, reason="прерван (сервер перезапустился)")
        await backfill_query_keys(session)
        await backfill_fingerprints(session)
        await restore_overmerged_duplicates(session)
        await backfill_company_icons(session)
    setup_tracing(app)
    bind_jobstore()
    if settings.runs_scheduler():
        start_scheduler()
        await sync_jobs()
        if settings.app_env != "test":
            import asyncio

            asyncio.create_task(run_internship_monitor_job())
            asyncio.create_task(run_hackathon_sync_job())
            asyncio.create_task(run_salary_market_job())
    yield


app = FastAPI(title="HuntOS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hunt_router)
app.include_router(contacts_router)
app.include_router(internships_router)
app.include_router(hackathons_router)
app.include_router(salary_market_router)
app.include_router(auth_router)
app.include_router(feedback_router)
app.include_router(chat_router)
app.include_router(vacancies_router)
app.include_router(settings_router)
app.include_router(google_router)
app.include_router(scraper_router)
app.include_router(telegram_router)
app.include_router(telegram_bot_router)

if settings.app_env != "test":
    # default() already exports http_requests_total + duration histograms.
    # status is grouped 2xx/4xx/5xx — alerts must use status="5xx", not 5..
    (
        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/api/health", "/api/ready", "/api/metrics"],
        )
        .add(metrics.default())
        .instrument(app)
        .expose(app, endpoint="/api/metrics", include_in_schema=False)
    )


@app.get("/api/health")
async def health() -> dict:
    """Liveness. Process is up. Do not touch the DB here — a locked sqlite
    must not make the orchestrator kill a still-serving API."""
    return {"ok": True, "status": "live"}


@app.get("/api/ready")
async def ready() -> dict:
    """Readiness. nginx / compose should gate on this, not /api/health."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="db") from exc
    return {"ok": True, "status": "ready"}
