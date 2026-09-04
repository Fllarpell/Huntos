from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from email.utils import parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.donor_cache import DonorListing, DonorQueryCache, DonorQueryListing
from app.models.scraper_config import ScraperConfig
from app.models.scraper_run import ScraperRun
from app.models.vacancy import PipelineStage, ScoringStatus, Vacancy
from app.models.vacancy_search import VacancySearch
from app.services.company_icon import hydrate_company_icon, normalize_company_icon
from app.services.extra_sources import compact_extra_sources, source_identity
from app.services.fingerprint import fingerprints_close, vacancy_fingerprint
from app.services.scraper.gate import outbound_gate
from app.services.scraper.http import PoliteHttp
from app.services.scraper.query_key import fetch_params, make_query_key
from app.services.scraper.registry import ADAPTERS as SOURCES
from app.services.scraper.registry import get_spec
from app.services.scraper.sources.hirehi import parse_listing_url
from app.services.scraper.listing_match import listing_matches_params
from app.services.scraper.sources.it_job_gate import listing_is_it_job
from app.services.scraper.sources.stack_lexicon import matching_stack_ids

log = logging.getLogger(__name__)

_SEED_CAP = 4000


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def config_params(config: ScraperConfig) -> dict:
    params = dict(config.query_params or {})
    if config.listing_url and not params:
        params = parse_listing_url(config.listing_url)
    return params


def donor_query_key(source: str, params: dict) -> str:
    return make_query_key(source, params)


def query_key_for(config: ScraperConfig) -> str:
    if config.query_key:
        return config.query_key
    return make_query_key(config.source, config_params(config))


def _payload_has_body(payload: dict) -> bool:
    return bool((payload.get("requirements") or payload.get("description") or "").strip())


async def _listing_by_source(
    session: AsyncSession, source: str, source_id: str
) -> DonorListing | None:
    return (
        await session.execute(
            select(DonorListing).where(DonorListing.source == source, DonorListing.source_id == source_id)
        )
    ).scalar_one_or_none()


async def upsert_donor_listing(session: AsyncSession, payload: dict) -> DonorListing:
    source = str(payload.get("source") or "")
    source_id = str(payload.get("source_id") or "")
    now = _now()
    row = await _listing_by_source(session, source, source_id)
    if row is None:
        row = DonorListing(
            source=source,
            source_id=source_id,
            payload=dict(payload),
            fetched_at=now,
            last_seen_at=now,
        )
        session.add(row)
        await session.flush()
        return row
    merged = dict(row.payload or {})
    for key, value in payload.items():
        if value not in (None, "", [], {}):
            if key in {"requirements", "description"} and merged.get(key) and not value:
                continue
            merged[key] = value
    row.payload = merged
    row.last_seen_at = now
    if not row.fetched_at:
        row.fetched_at = now
    return row


async def _link_query_listing(session: AsyncSession, query_id: int, listing_id: int) -> None:
    existing = (
        await session.execute(
            select(DonorQueryListing).where(
                DonorQueryListing.query_id == query_id,
                DonorQueryListing.listing_id == listing_id,
            )
        )
    ).scalar_one_or_none()
    now = _now()
    if existing is None:
        session.add(DonorQueryListing(query_id=query_id, listing_id=listing_id, last_seen_at=now))
        return
    existing.last_seen_at = now


async def listings_for_query(session: AsyncSession, query_id: int) -> list[DonorListing]:
    rows = (
        await session.execute(
            select(DonorListing)
            .join(DonorQueryListing, DonorQueryListing.listing_id == DonorListing.id)
            .where(DonorQueryListing.query_id == query_id)
            .order_by(DonorListing.id.desc())
        )
    ).scalars()
    return list(rows.all())


async def fanout_listings(
    session: AsyncSession,
    listings: list[DonorListing],
    *,
    user_id: int,
    scraper_config_id: int | None,
    source: str | None = None,
    query_params: dict | None = None,
) -> tuple[int, int, int]:
    new_count = 0
    updated_count = 0
    matched = 0
    for listing in listings:
        payload = dict(listing.payload or {})
        if not payload.get("source"):
            payload["source"] = listing.source
        if not payload.get("source_id"):
            payload["source_id"] = listing.source_id
        if query_params is not None:
            if not listing_matches_params(payload, source or listing.source, query_params):
                continue
        elif not listing_is_it_job(payload):
            continue
        matched += 1
        _, kind = await upsert_vacancy(
            session, payload, scraper_config_id=scraper_config_id, user_id=user_id
        )
        if kind == "new":
            new_count += 1
        else:
            updated_count += 1
        await session.commit()
    from app.services.thesis import refresh_user_theses

    await refresh_user_theses(session, user_id, commit=True)
    return matched, new_count, updated_count


async def seed_listings_for_config(session: AsyncSession, config: ScraperConfig) -> list[DonorListing]:
    """Reuse any already-fetched vacancy that matches this search (go = golang = Go chip)."""
    key = query_key_for(config)
    params = config_params(config)
    source = config.source
    found: dict[int, DonorListing] = {}
    cache = (
        await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key == key))
    ).scalar_one_or_none()
    if cache is not None:
        for row in await listings_for_query(session, cache.id):
            payload = dict(row.payload or {})
            payload.setdefault("source", row.source)
            payload.setdefault("source_id", row.source_id)
            if listing_matches_params(payload, source, params):
                found[row.id] = row
    stmt = (
        select(DonorListing)
        .where(DonorListing.source == source)
        .order_by(DonorListing.id.desc())
        .limit(_SEED_CAP)
    )
    if source == "career":
        company = str((params or {}).get("company") or "").strip().lower()
        if company:
            stmt = (
                select(DonorListing)
                .where(
                    DonorListing.source == source,
                    DonorListing.source_id.like(f"{company}:%"),
                )
                .order_by(DonorListing.id.desc())
                .limit(_SEED_CAP)
            )
    for row in (await session.execute(stmt)).scalars().all():
        if row.id in found:
            continue
        payload = dict(row.payload or {})
        payload.setdefault("source", row.source)
        payload.setdefault("source_id", row.source_id)
        if listing_matches_params(payload, source, params):
            found[row.id] = row
    return list(found.values())


async def remember_seed_cache(
    session: AsyncSession,
    config: ScraperConfig,
    listings: list[DonorListing],
) -> DonorQueryCache:
    cache = await _get_or_create_query(session, config)
    for listing in listings:
        await _link_query_listing(session, cache.id, listing.id)
    if cache.last_fetched_at is None:
        cache.last_fetched_at = _now()
        cache.last_status = "ok"
        cache.found_count = len(listings)
        cache.last_error = None
    await session.commit()
    return cache


async def deliver_from_pool(
    session: AsyncSession,
    config: ScraperConfig,
) -> tuple[int, int, int] | None:
    """Copy matching donor listings into this inbox. None = nothing cached yet."""
    if not config.user_id:
        return None
    listings = await seed_listings_for_config(session, config)
    if not listings:
        return None
    await remember_seed_cache(session, config, listings)
    return await fanout_listings(
        session,
        listings,
        user_id=config.user_id,
        scraper_config_id=config.id,
        source=config.source,
        query_params=config_params(config),
    )


async def _siblings(session: AsyncSession, config: ScraperConfig) -> list[ScraperConfig]:
    key = query_key_for(config)
    rows = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    found = [row for row in rows if query_key_for(row) == key]
    if config.id and not any(row.id == config.id for row in found):
        found.append(config)
    return found or [config]


def _cache_fresh(cache: DonorQueryCache, ttl_minutes: int) -> bool:
    if cache.last_status != "ok" or cache.last_fetched_at is None:
        return False
    ttl = max(ttl_minutes, settings.scraper_global_min_interval_minutes, 5)
    return _now() - cache.last_fetched_at < timedelta(minutes=ttl)


async def _get_or_create_query(
    session: AsyncSession, config: ScraperConfig
) -> DonorQueryCache:
    params = fetch_params(config.source, config_params(config))
    key = donor_query_key(config.source, params)
    row = (
        await session.execute(select(DonorQueryCache).where(DonorQueryCache.query_key == key))
    ).scalar_one_or_none()
    config.query_key = key
    if row is not None:
        row.query_params = params
        row.listing_url = config.listing_url
        return row
    row = DonorQueryCache(
        query_key=key,
        source=config.source,
        query_params=params,
        listing_url=config.listing_url,
        last_status="idle",
    )
    session.add(row)
    await session.flush()
    return row


async def _crawl_donor(
    session: AsyncSession,
    cache: DonorQueryCache,
    *,
    max_pages: int,
) -> tuple[list[DonorListing], int, str | None]:
    source_cls = SOURCES.get(cache.source)
    if source_cls is None:
        return [], 0, f"Unknown source: {cache.source}"
    params = fetch_params(cache.source, cache.query_params)
    source = source_cls(PoliteHttp())
    found = 0
    seen: list[DonorListing] = []
    error: str | None = None
    spec = get_spec(cache.source)
    page_limit = spec.page_limit if spec else 20
    max_details = min(250, max(40, max_pages * min(page_limit, 25)))
    details_fetched = 0
    async with outbound_gate(cache.source):
        try:
            if hasattr(source, "open"):
                await source.open(params)
            page = 1
            while page <= max_pages:
                data = await source.search(params, page=page, limit=page_limit)
                jobs = data.get("jobs") or data.get("items") or []
                found += len(jobs)
                log.info("%s page %s: %s jobs (host cache)", cache.source, page, len(jobs))
                for item in jobs:
                    job_id = item.get("id")
                    if job_id is None:
                        continue
                    if item.get("title") and not listing_is_it_job(item):
                        continue
                    listing = await _listing_by_source(session, cache.source, str(job_id))
                    if listing is not None and _payload_has_body(listing.payload or {}):
                        if not listing_is_it_job({**(listing.payload or {}), **item}):
                            continue
                        listing.last_seen_at = _now()
                        await _link_query_listing(session, cache.id, listing.id)
                        seen.append(listing)
                        await session.commit()
                        continue
                    payload: dict
                    if details_fetched >= max_details:
                        payload = source.normalize(item, item)
                    else:
                        try:
                            detail = await source.detail(job_id, params)
                            details_fetched += 1
                            payload = source.normalize(detail, item)
                        except Exception as exc:
                            log.warning("detail failed %s/%s: %s", cache.source, job_id, exc)
                            payload = source.normalize(item, item)
                    if not listing_is_it_job(payload):
                        continue
                    listing = await upsert_donor_listing(session, payload)
                    await _link_query_listing(session, cache.id, listing.id)
                    seen.append(listing)
                    await session.commit()
                if not data.get("has_more"):
                    break
                page += 1
        except Exception as exc:  # noqa: BLE001 — persist the cache row, don't crash cron
            log.exception("Host donor crawl failed")
            await session.rollback()
            error = str(exc)[:2000]
            cache = await session.get(DonorQueryCache, cache.id) or cache
            seen = await listings_for_query(session, cache.id)
        finally:
            if hasattr(source, "close"):
                try:
                    await source.close()
                except Exception:
                    pass
    return seen, found, error


_FULL_SERP = frozenset({"hh", "habr", "geekjob", "getmatch"})


def crawl_max_pages(source: str, siblings: list) -> int:
    """Wide SERPs used to be stored as max_pages=1/3 and never grew past the first screen."""
    spec = get_spec(source)
    stored = max((getattr(row, "max_pages", 0) or 0) for row in siblings) if siblings else 0
    default = spec.default_max_pages if spec else 1
    cap = settings.scraper_max_pages
    if spec and spec.id in _FULL_SERP:
        cap = max(cap, default)
    return min(max(stored, default, 1), cap)


async def refresh_query_cache(
    session: AsyncSession,
    config: ScraperConfig,
    *,
    force: bool = False,
) -> tuple[DonorQueryCache, list[DonorListing], bool]:
    """Fetch hh/HireHi only when the shared cache is stale. Always host-side."""
    siblings = await _siblings(session, config)
    ttl = max(settings.scraper_cache_ttl_minutes, settings.scraper_global_min_interval_minutes, 5)
    max_pages = crawl_max_pages(config.source, siblings)
    cache = await _get_or_create_query(session, config)
    await session.commit()
    if not force and _cache_fresh(cache, ttl):
        listings = await listings_for_query(session, cache.id)
        if listings:
            return cache, listings, True
        seeded = await seed_listings_for_config(session, config)
        return cache, seeded, True
    listings, found, error = await _crawl_donor(session, cache, max_pages=max_pages)
    cache = await session.get(DonorQueryCache, cache.id)
    if cache is None:
        cache = await _get_or_create_query(session, config)
    cache.last_fetched_at = _now()
    cache.found_count = found
    if error:
        cache.last_status = "error"
        cache.last_error = error
    else:
        cache.last_status = "ok"
        cache.last_error = None
    await session.commit()
    return cache, listings, False


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


def extra_source_label(source: object, source_id: object, source_url: object = None) -> str:
    key = str(source or "").strip()
    if key == "career":
        from app.services.scraper.sources.career_catalog import get_board

        slug = str(source_id or "").split(":", 1)[0]
        board = get_board(slug)
        if board:
            return board.name
        return "сайт компании"
    labels = {
        "hh": "hh.ru",
        "hirehi": "HireHi",
        "habr": "Habr Career",
        "getmatch": "GetMatch",
        "geekjob": "GeekJob",
        "telegram": "Telegram",
        "clip": "клиппер",
        "manual": "вручную",
    }
    return labels.get(key, key or str(source_url or "другая площадка"))


_SKIP_PAYLOAD = {
    "published_at",
    "user_id",
    "extra_sources",
    "duplicate_of_id",
    "id",
    "scraper_config_id",
    "scoring_status",
    "fingerprint",
    "last_seen_at",
    "stage_entered_at",
    "pipeline_stage",
}


def _vacancy_kwargs(payload: dict) -> dict:
    allowed = {column.key for column in Vacancy.__table__.columns}
    return {key: value for key, value in payload.items() if key in allowed and key not in _SKIP_PAYLOAD}


def _source_entry(payload: dict) -> dict:
    source = payload.get("source")
    source_id = str(payload.get("source_id") or "")
    source_url = payload.get("source_url")
    return {
        "source": source,
        "source_id": source_id,
        "source_url": source_url,
        "label": extra_source_label(source, source_id, source_url),
    }


def _stacks_from_vacancy(vacancy: Vacancy) -> list[str]:
    skills = vacancy.skills or []
    skill_text = " ".join(str(item) for item in skills) if isinstance(skills, list) else str(skills)
    return matching_stack_ids(vacancy.title, vacancy.category, skill_text, vacancy.tags)


def _merge_into(canonical: Vacancy, payload: dict) -> None:
    extra = list(canonical.extra_sources or [])
    extra.append(_source_entry(payload))
    canonical.extra_sources = compact_extra_sources(
        extra, source=canonical.source, source_id=canonical.source_id
    )
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
    skills = list(canonical.skills or [])
    incoming_skills = payload.get("skills") or []
    if isinstance(incoming_skills, list):
        for item in incoming_skills:
            text = str(item).strip()
            if text and text not in skills:
                skills.append(text)
        canonical.skills = skills[:24]
    canonical.stack_ids = _stacks_from_vacancy(canonical)


async def remember_search(session: AsyncSession, vacancy: Vacancy, scraper_config_id: int | None) -> None:
    if not scraper_config_id or vacancy.id is None:
        return
    vacancy.scraper_config_id = scraper_config_id
    exists = (
        await session.execute(
            select(VacancySearch).where(
                VacancySearch.vacancy_id == vacancy.id,
                VacancySearch.scraper_config_id == scraper_config_id,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(VacancySearch(vacancy_id=vacancy.id, scraper_config_id=scraper_config_id))


async def _stack_for(session: AsyncSession, payload: dict, scraper_config_id: int | None) -> list[str]:
    """Detect stacks from vacancy content only.

    Never copy the search's stack chips onto the card — a crawl with «все стеки»
    used to stamp every vacancy with the full stack list, so inbox filter
    ``nlp`` → ``ml`` matched Java/SRE/PM noise.
    """
    _ = session, scraper_config_id
    skills = payload.get("skills") or []
    if isinstance(skills, list):
        skill_text = " ".join(str(item) for item in skills)
    else:
        skill_text = str(skills)
    return matching_stack_ids(
        payload.get("title"),
        payload.get("category"),
        skill_text,
        payload.get("tags"),
    )


def _has_identity(vacancy: Vacancy, source: str, source_id: str) -> bool:
    ident = source_identity(source, source_id)
    if not ident:
        return False
    if source_identity(vacancy.source, vacancy.source_id) == ident:
        return True
    for item in vacancy.extra_sources or []:
        if not isinstance(item, dict):
            continue
        if source_identity(item.get("source"), item.get("source_id")) == ident:
            return True
    return False


async def _find_twin(
    session: AsyncSession,
    *,
    user_id: int,
    fp: str,
    source: str,
    source_id: str,
    stack_ids: list[str] | None = None,
) -> Vacancy | None:
    if not fp or fp == "|":
        return None
    exact = (
        await session.execute(
            select(Vacancy).where(
                Vacancy.user_id == user_id,
                Vacancy.fingerprint == fp,
                Vacancy.duplicate_of_id.is_(None),
            )
        )
    ).scalars().all()
    for row in exact:
        if _has_identity(row, source, source_id):
            continue
        return row
    prefix = fp.split("|", 1)[0]
    if not prefix or prefix == "nda":
        return None
    candidates = (
        await session.execute(
            select(Vacancy).where(
                Vacancy.user_id == user_id,
                Vacancy.duplicate_of_id.is_(None),
                Vacancy.fingerprint.like(f"{prefix}|%"),
            )
        )
    ).scalars().all()
    for row in candidates:
        if _has_identity(row, source, source_id):
            continue
        if fingerprints_close(fp, row.fingerprint, stack_ids, row.stack_ids):
            return row
    return None


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
    payload["stack_ids"] = await _stack_for(session, payload, scraper_config_id)

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
                canonical.stack_ids = _stacks_from_vacancy(canonical)
                await remember_search(session, canonical, scraper_config_id)
                await remember_search(session, existing, scraper_config_id)
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
            if key in {"published_at", "notes", "telegram_alias", "user_id", "fingerprint", "extra_sources", "stack_ids"}:
                continue
            if key == "company_icon":
                incoming_icon = normalize_company_icon(value, page_url=payload.get("source_url") or existing.source_url)
                if incoming_icon and not normalize_company_icon(existing.company_icon, page_url=existing.source_url):
                    existing.company_icon = incoming_icon
                continue
            setattr(existing, key, value)
        existing.published_at = published or existing.published_at
        existing.last_seen_at = now
        existing.fingerprint = fp
        existing.stack_ids = _stacks_from_vacancy(existing)
        await remember_search(session, existing, scraper_config_id)
        if changed and existing.pipeline_stage == PipelineStage.INBOX:
            existing.scoring_status = ScoringStatus.PENDING
            existing.match_score = None
            existing.match_rationale = None
        await hydrate_company_icon(session, existing)
        return existing, "updated"

    twin = await _find_twin(
        session,
        user_id=user_id,
        fp=fp,
        source=str(payload.get("source") or ""),
        source_id=str(payload.get("source_id") or ""),
        stack_ids=payload.get("stack_ids"),
    )
    if twin is not None:
        _merge_into(twin, payload)
        twin.last_seen_at = now
        twin.fingerprint = twin.fingerprint or fp
        twin.stack_ids = _stacks_from_vacancy(twin)
        if published and (twin.published_at is None or published > twin.published_at):
            twin.published_at = published
        stub = Vacancy(
            **_vacancy_kwargs(payload),
            user_id=user_id,
            published_at=published,
            last_seen_at=now,
            scraper_config_id=scraper_config_id,
            scoring_status=ScoringStatus.SKIPPED,
            fingerprint=fp,
            extra_sources=[],
            duplicate_of_id=twin.id,
            stage_entered_at=now,
            pipeline_stage=PipelineStage.INBOX,
        )
        session.add(stub)
        await session.flush()
        await remember_search(session, twin, scraper_config_id)
        await remember_search(session, stub, scraper_config_id)
        await hydrate_company_icon(session, twin)
        return twin, "merged"

    vacancy = Vacancy(
        **_vacancy_kwargs(payload),
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
    await remember_search(session, vacancy, scraper_config_id)
    await hydrate_company_icon(session, vacancy)
    return vacancy, "new"


async def run_config(
    session: AsyncSession,
    config: ScraperConfig,
    *,
    force: bool = False,
    process: bool = True,
) -> ScraperRun:
    from app.services.scraper.queue import (
        enqueue_query,
        ensure_config_key,
        ensure_queued_run,
        process_query_key,
    )

    if not config.user_id:
        run = ScraperRun(
            scraper_config_id=config.id,
            user_id=config.user_id,
            started_at=_now(),
            status="error",
            error="Поиск без владельца — войди в аккаунт",
            finished_at=_now(),
        )
        session.add(run)
        await session.commit()
        return run

    if config.source not in SOURCES:
        run = ScraperRun(
            scraper_config_id=config.id,
            user_id=config.user_id,
            started_at=_now(),
            status="error",
            error=f"Unknown source: {config.source}",
            finished_at=_now(),
        )
        session.add(run)
        await session.commit()
        return run

    ensure_config_key(config)
    if not force:
        delivered = await deliver_from_pool(session, config)
        if delivered is not None:
            found, new_count, updated_count = delivered
            run = await ensure_queued_run(session, config)
            run.status = "ok"
            run.error = None
            run.found_count = found
            run.new_count = new_count
            run.updated_count = updated_count
            run.finished_at = _now()
            await session.commit()
            return run
    run = await ensure_queued_run(session, config)
    await enqueue_query(session, config=config, force=force)
    if process:
        await process_query_key(session, config.query_key or query_key_for(config))
        latest = (
            await session.execute(
                select(ScraperRun)
                .where(ScraperRun.scraper_config_id == config.id)
                .order_by(ScraperRun.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is not None and latest.status not in {"queued", "running"}:
            return latest
        cache, listings, _from_cache = await refresh_query_cache(session, config, force=force)
        found, new_count, updated_count = await fanout_listings(
            session,
            listings,
            user_id=config.user_id,
            scraper_config_id=config.id,
            source=config.source,
            query_params=config_params(config),
        )
        run = latest or run
        if cache.last_status == "error" and not listings:
            run.status = "error"
            run.error = cache.last_error
        else:
            run.status = "ok"
            run.error = cache.last_error if cache.last_status == "error" else None
        run.found_count = found if found else cache.found_count
        run.new_count = new_count
        run.updated_count = updated_count
        run.finished_at = _now()
        await session.commit()
        return run
    return run


async def run_query_key(session: AsyncSession, query_key: str) -> list[ScraperRun]:
    from app.services.scraper.queue import enqueue_query, process_query_key

    sample = (
        await session.execute(
            select(ScraperConfig).where(
                ScraperConfig.enabled.is_(True),
                ScraperConfig.user_id.is_not(None),
            )
        )
    ).scalars().all()
    configs = [row for row in sample if query_key_for(row) == query_key]
    if not configs:
        return []
    await enqueue_query(session, query_key=query_key, source=configs[0].source, force=False)
    await process_query_key(session, query_key)
    runs = (
        await session.execute(
            select(ScraperRun)
            .where(ScraperRun.scraper_config_id.in_([row.id for row in configs]))
            .order_by(ScraperRun.id.desc())
        )
    ).scalars().all()
    latest: dict[int, ScraperRun] = {}
    for run in runs:
        if run.scraper_config_id and run.scraper_config_id not in latest:
            latest[run.scraper_config_id] = run
    return list(latest.values())


async def run_all_enabled(session: AsyncSession) -> list[ScraperRun]:
    from app.services.scraper.queue import drain_queue, enqueue_due_queries

    await enqueue_due_queries(session)
    await drain_queue(session)
    result = await session.execute(select(ScraperRun).order_by(ScraperRun.id.desc()).limit(40))
    return list(result.scalars().all())


async def backfill_fingerprints(session: AsyncSession) -> int:
    """Fill empty fingerprints and recompute stack_ids from content (not search chips)."""
    rows = (await session.execute(select(Vacancy))).scalars().all()
    changed = 0
    for vacancy in rows:
        fp = vacancy_fingerprint(vacancy.title, vacancy.company)
        if vacancy.fingerprint != fp:
            vacancy.fingerprint = fp
            changed += 1
        skills = vacancy.skills or []
        skill_text = " ".join(str(item) for item in skills) if isinstance(skills, list) else str(skills)
        detected = matching_stack_ids(vacancy.title, skill_text, vacancy.tags, vacancy.category)
        if list(vacancy.stack_ids or []) != detected:
            vacancy.stack_ids = detected
            changed += 1
    if changed:
        await session.commit()
    return changed


async def restore_overmerged_duplicates(session: AsyncSession) -> int:
    """Bring back listings that fingerprint-merge hid. Keep at most one extra per other board."""
    rows = (await session.execute(select(Vacancy))).scalars().all()
    by_id = {row.id: row for row in rows}
    stubs = [row for row in rows if row.duplicate_of_id]
    keep: set[int] = set()
    groups: dict[tuple[int, str], list[Vacancy]] = {}
    for stub in stubs:
        parent = by_id.get(stub.duplicate_of_id)
        if parent is None:
            continue
        ident = source_identity(stub.source, stub.source_id)
        parent_ident = source_identity(parent.source, parent.source_id)
        if not ident or ident == parent_ident:
            continue
        groups.setdefault((parent.id, ident), []).append(stub)
    for group in groups.values():
        group.sort(key=lambda row: row.id)
        keep.add(group[0].id)
    restored = 0
    for stub in stubs:
        if stub.id in keep:
            continue
        stub.duplicate_of_id = None
        if stub.scoring_status == ScoringStatus.SKIPPED:
            stub.scoring_status = ScoringStatus.PENDING
        restored += 1
    if not restored:
        return 0
    for vacancy in rows:
        vacancy.extra_sources = compact_extra_sources(
            vacancy.extra_sources, source=vacancy.source, source_id=vacancy.source_id
        )
    await session.commit()
    return restored
