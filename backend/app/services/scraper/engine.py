from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from email.utils import parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scraper_config import ScraperConfig
from app.models.scraper_run import ScraperRun
from app.models.vacancy import PipelineStage, ScoringStatus, Vacancy
from app.services.company_icon import hydrate_company_icon, normalize_company_icon
from app.services.fingerprint import vacancy_fingerprint
from app.services.scraper.http import PoliteHttp
from app.services.scraper.sources.hh import HhSource
from app.services.scraper.sources.hirehi import HireHiSource, parse_listing_url

log = logging.getLogger(__name__)

SOURCES = {
    "hirehi": HireHiSource,
    "hh": HhSource,
}


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def fail_open_runs(
    session: AsyncSession,
    *,
    reason: str,
    older_than: timedelta | None = None,
    user_id: int | None = None,
) -> int:
    stmt = select(ScraperRun).where(ScraperRun.status == "running")
    if older_than is not None:
        stmt = stmt.where(ScraperRun.started_at < _now() - older_than)
    if user_id is not None:
        stmt = stmt.where(ScraperRun.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    now = _now()
    for run in rows:
        run.status = "error"
        run.error = reason
        run.finished_at = now
    if rows:
        await session.commit()
    return len(rows)


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return _utc_naive(value)
    text = str(value).strip()
    try:
        parsed = parsedate_to_datetime(text)
        return _utc_naive(parsed)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _utc_naive(parsed)
    except ValueError:
        return None


def _content_fingerprint(payload: dict) -> tuple[str, str, str]:
    return (
        (payload.get("title") or "").strip(),
        (payload.get("requirements") or "").strip(),
        (payload.get("description") or "").strip()[:400],
    )


def _source_entry(payload: dict) -> dict:
    return {
        "source": payload.get("source"),
        "source_id": str(payload.get("source_id") or ""),
        "source_url": payload.get("source_url"),
    }


def _merge_into(canonical: Vacancy, payload: dict) -> None:
    extra = list(canonical.extra_sources or [])
    entry = _source_entry(payload)
    same = any(
        item.get("source") == entry["source"] and str(item.get("source_id")) == entry["source_id"] for item in extra
    )
    if not same and (canonical.source != entry["source"] or canonical.source_id != entry["source_id"]):
        extra.append(entry)
    canonical.extra_sources = extra
    if not canonical.telegram_alias and payload.get("telegram_alias"):
        canonical.telegram_alias = payload["telegram_alias"]
    if canonical.salary_min is None and payload.get("salary_min"):
        canonical.salary_min = payload.get("salary_min")
        canonical.salary_max = payload.get("salary_max") or canonical.salary_max
        canonical.salary_raw = payload.get("salary_raw") or canonical.salary_raw
        canonical.salary_currency = payload.get("salary_currency") or canonical.salary_currency
    if not canonical.requirements and payload.get("requirements"):
        canonical.requirements = payload["requirements"]
        if canonical.pipeline_stage == PipelineStage.INBOX:
            canonical.scoring_status = ScoringStatus.PENDING
            canonical.match_score = None
    if not canonical.source_url and payload.get("source_url"):
        canonical.source_url = payload["source_url"]
    incoming_icon = normalize_company_icon(payload.get("company_icon"), page_url=payload.get("source_url"))
    if incoming_icon and not normalize_company_icon(canonical.company_icon, page_url=canonical.source_url):
        canonical.company_icon = incoming_icon
    tags = list(canonical.tags or [])
    src = payload.get("source")
    if src and src not in tags:
        tags.append(str(src))
    canonical.tags = tags[:24]


async def upsert_vacancy(
    session: AsyncSession,
    payload: dict,
    *,
    scraper_config_id: int | None,
    user_id: int,
) -> tuple[Vacancy, str]:
    result = await session.execute(
        select(Vacancy).where(
            Vacancy.user_id == user_id,
            Vacancy.source == payload["source"],
            Vacancy.source_id == payload["source_id"],
        )
    )
    existing = result.scalar_one_or_none()
    now = _now()
    published = _parse_dt(payload.get("published_at"))
    fp = vacancy_fingerprint(payload.get("title"), payload.get("company"))
    payload["company_icon"] = normalize_company_icon(
        payload.get("company_icon"), page_url=payload.get("source_url")
    )

    if existing is not None:
        canonical = existing
        if existing.duplicate_of_id:
            parent = await session.get(Vacancy, existing.duplicate_of_id)
            if parent is not None:
                canonical = parent
                _merge_into(canonical, payload)
                existing.last_seen_at = now
                existing.fingerprint = fp
                canonical.last_seen_at = now
                await hydrate_company_icon(session, canonical)
                return canonical, "merged"
        changed = _content_fingerprint(
            {
                "title": existing.title,
                "requirements": existing.requirements,
                "description": existing.description,
            }
        ) != _content_fingerprint(payload)

        for key, value in payload.items():
            if key in {"published_at", "notes", "telegram_alias", "user_id", "fingerprint", "extra_sources"}:
                continue
            if key == "company_icon":
                incoming_icon = normalize_company_icon(value, page_url=payload.get("source_url") or existing.source_url)
                if incoming_icon and not normalize_company_icon(existing.company_icon, page_url=existing.source_url):
                    existing.company_icon = incoming_icon
                continue
            setattr(existing, key, value)
        existing.published_at = published or existing.published_at
        existing.last_seen_at = now
        existing.scraper_config_id = scraper_config_id
        existing.fingerprint = fp
        if changed and existing.pipeline_stage == PipelineStage.INBOX:
            existing.scoring_status = ScoringStatus.PENDING
            existing.match_score = None
            existing.match_rationale = None
        await hydrate_company_icon(session, existing)
        return existing, "updated"

    if fp and fp != "|":
        twin = (
            await session.execute(
                select(Vacancy).where(
                    Vacancy.user_id == user_id,
                    Vacancy.fingerprint == fp,
                    Vacancy.duplicate_of_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if twin is not None:
            _merge_into(twin, payload)
            twin.last_seen_at = now
            twin.fingerprint = fp
            if published and (twin.published_at is None or published > twin.published_at):
                twin.published_at = published
            await hydrate_company_icon(session, twin)
            return twin, "merged"

    vacancy = Vacancy(
        **{k: v for k, v in payload.items() if k not in {"published_at", "user_id"}},
        user_id=user_id,
        published_at=published,
        last_seen_at=now,
        scraper_config_id=scraper_config_id,
        scoring_status=ScoringStatus.PENDING,
        fingerprint=fp,
        extra_sources=[],
        stage_entered_at=now,
    )
    session.add(vacancy)
    await session.flush()
    await hydrate_company_icon(session, vacancy)
    return vacancy, "new"


async def run_config(session: AsyncSession, config: ScraperConfig) -> ScraperRun:
    run = ScraperRun(
        scraper_config_id=config.id,
        user_id=config.user_id,
        started_at=_now(),
        status="running",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    run_id = run.id
    config_id = config.id
    user_id = config.user_id
    source_name = config.source

    if not user_id:
        run.status = "error"
        run.error = "Поиск без владельца — войди в аккаунт"
        run.finished_at = _now()
        await session.commit()
        return run

    params = dict(config.query_params or {})
    if config.listing_url and not params:
        params = parse_listing_url(config.listing_url)

    source_cls = SOURCES.get(source_name)
    if source_cls is None:
        run.status = "error"
        run.error = f"Unknown source: {source_name}"
        run.finished_at = _now()
        await session.commit()
        return run

    source = source_cls(PoliteHttp())
    found = 0
    new_count = 0
    updated_count = 0
    details_fetched = 0
    max_pages = min(config.max_pages or settings.scraper_max_pages, settings.scraper_max_pages)
    max_details = 40
    status = "ok"
    error: str | None = None

    try:
        if hasattr(source, "open"):
            await source.open(params)
        page = 1
        while page <= max_pages:
            data = await source.search(params, page=page, limit=50 if source_name == "hh" else 20)
            jobs = data.get("jobs") or data.get("items") or []
            found += len(jobs)
            log.info("%s page %s: %s jobs", source_name, page, len(jobs))
            for item in jobs:
                job_id = item.get("id")
                if job_id is None:
                    continue
                existing = await session.execute(
                    select(Vacancy).where(
                        Vacancy.user_id == user_id,
                        Vacancy.source == source_name,
                        Vacancy.source_id == str(job_id),
                    )
                )
                row = existing.scalar_one_or_none()
                if row and row.requirements:
                    row.last_seen_at = _now()
                    updated_count += 1
                    await session.commit()
                    continue
                if details_fetched >= max_details:
                    if row is None:
                        payload = source.normalize(item, item)
                        _, kind = await upsert_vacancy(
                            session, payload, scraper_config_id=config_id, user_id=user_id
                        )
                        if kind == "new":
                            new_count += 1
                        else:
                            updated_count += 1
                        await session.commit()
                    continue
                try:
                    detail = await source.detail(job_id, params)
                except Exception as exc:
                    log.warning("detail failed %s/%s: %s", source_name, job_id, exc)
                    payload = source.normalize(item, item)
                    _, kind = await upsert_vacancy(
                        session, payload, scraper_config_id=config_id, user_id=user_id
                    )
                    if kind == "new":
                        new_count += 1
                    else:
                        updated_count += 1
                    await session.commit()
                    continue
                details_fetched += 1
                payload = source.normalize(detail, item)
                _, kind = await upsert_vacancy(
                    session, payload, scraper_config_id=config_id, user_id=user_id
                )
                if kind == "new":
                    new_count += 1
                else:
                    updated_count += 1
                await session.commit()
            if not data.get("has_more"):
                break
            page += 1
    except Exception as exc:  # noqa: BLE001 — persist the run, don't crash cron
        log.exception("Scraper failed")
        await session.rollback()
        status = "error"
        error = str(exc)[:2000]
    finally:
        if hasattr(source, "close"):
            try:
                await source.close()
            except Exception:
                pass

    run = await session.get(ScraperRun, run_id)
    if run is None:
        run = ScraperRun(scraper_config_id=config_id, user_id=user_id, started_at=_now())
        session.add(run)
    run.status = status
    run.error = error
    run.found_count = found
    run.new_count = new_count
    run.updated_count = updated_count
    run.finished_at = _now()
    await session.commit()
    return run


async def run_all_enabled(session: AsyncSession) -> list[ScraperRun]:
    result = await session.execute(select(ScraperConfig).where(ScraperConfig.enabled.is_(True)))
    configs = result.scalars().all()
    runs: list[ScraperRun] = []
    for config in configs:
        try:
            runs.append(await run_config(session, config))
        except Exception:
            # run_config already stored the error row
            continue
    return runs


async def backfill_fingerprints(session: AsyncSession) -> int:
    rows = (await session.execute(select(Vacancy))).scalars().all()
    grouped: dict[tuple[int, str], list[Vacancy]] = {}
    for vacancy in rows:
        vacancy.fingerprint = vacancy_fingerprint(vacancy.title, vacancy.company)
        if vacancy.user_id is None or not vacancy.fingerprint:
            continue
        grouped.setdefault((vacancy.user_id, vacancy.fingerprint), []).append(vacancy)
    merged = 0
    for items in grouped.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda row: row.id)
        canonical = next((row for row in items if row.duplicate_of_id is None), items[0])
        for other in items:
            if other.id == canonical.id or other.duplicate_of_id:
                continue
            other.duplicate_of_id = canonical.id
            _merge_into(
                canonical,
                {
                    "source": other.source,
                    "source_id": other.source_id,
                    "source_url": other.source_url,
                    "telegram_alias": other.telegram_alias,
                    "salary_min": other.salary_min,
                    "salary_max": other.salary_max,
                    "salary_raw": other.salary_raw,
                    "salary_currency": other.salary_currency,
                    "requirements": other.requirements,
                },
            )
            merged += 1
    if merged or rows:
        await session.commit()
    return merged
