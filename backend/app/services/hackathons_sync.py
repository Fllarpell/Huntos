"""Fetch hackathon calendars and upsert into hackathon_events."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hackathon_event import HackathonEvent
from app.services.hackathons_parse import (
    HACKPRO_ACTIVE,
    HACKPRO_ARCHIVE,
    HACKRUS_PAST,
    HACKRUS_RESULTS,
    HACKRUS_UPCOMING,
    ODS_PAGE,
    SOURCE_REFERERS,
    TILDA_FEED,
    parse_ods_page,
    parse_tilda_feed,
)
from app.services.scraper.http import PoliteHttp


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def compute_is_new(
    *,
    event_status: str | None,
    registration_status: str | None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    now: datetime | None = None,
) -> bool:
    """Live events only: registration open or currently running. Finished is never new."""
    moment = now or _now()
    status = (event_status or "").strip().lower()
    if status == "finished":
        return False
    if ends_at is not None and ends_at < moment:
        return False
    if (registration_status or "").strip().lower() == "open":
        return True
    if status == "active":
        return True
    if starts_at is not None and ends_at is not None and starts_at <= moment <= ends_at:
        return True
    return False


async def _fetch_tilda(
    http: PoliteHttp,
    feeduid: str,
    recid: str,
    *,
    referer: str,
    size: int = 50,
) -> dict:
    return await http.get_json(
        TILDA_FEED,
        params={"feeduid": feeduid, "recid": recid, "c": "1", "size": str(size)},
        referer=referer,
        timeout=30.0,
    )


async def collect_events(http: PoliteHttp | None = None) -> tuple[list[dict], list[str]]:
    client = http or PoliteHttp()
    events: list[dict] = []
    errors: list[str] = []

    feeds = [
        ("hackrus", HACKRUS_UPCOMING, "upcoming"),
        ("hackrus", HACKRUS_PAST, "finished"),
        ("hackrus", HACKRUS_RESULTS, "finished"),
        ("hackathons_pro", HACKPRO_ACTIVE, "active"),
        ("hackathons_pro", HACKPRO_ARCHIVE, "finished"),
    ]
    for source, (feeduid, recid), status in feeds:
        try:
            payload = await _fetch_tilda(
                client,
                feeduid,
                recid,
                referer=SOURCE_REFERERS[source],
            )
            events.extend(parse_tilda_feed(payload, source=source, default_event_status=status))
        except Exception as exc:
            errors.append(f"{source}:{feeduid}: {exc}"[:300])
        await asyncio.sleep(0.15)

    try:
        html = await client.get_text(ODS_PAGE, referer=SOURCE_REFERERS["ods"], timeout=30.0)
        events.extend(parse_ods_page(html))
    except Exception as exc:
        errors.append(f"ods: {exc}"[:300])

    return events, errors


def _merge_key(item: dict) -> tuple[str, str]:
    return str(item["source"]), str(item["source_id"])


async def refresh_hackathons(session: AsyncSession) -> dict[str, int]:
    scraped, errors = await collect_events()
    now = _now()
    by_key = {_merge_key(item): item for item in scraped}
    existing = (await session.execute(select(HackathonEvent))).scalars().all()
    seen: set[tuple[str, str]] = set()
    created = updated = 0

    for row in existing:
        key = (row.source, row.source_id)
        item = by_key.get(key)
        if item is None:
            if row.event_status != "finished" and row.last_seen_at < now - timedelta(days=14):
                row.event_status = "finished"
                row.registration_status = "closed"
                row.is_new = False
                updated += 1
            else:
                row.is_new = compute_is_new(
                    event_status=row.event_status,
                    registration_status=row.registration_status,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    now=now,
                )
            continue
        seen.add(key)
        row.title = item["title"]
        row.url = item["url"]
        row.description = item.get("description")
        row.starts_at = item.get("starts_at")
        row.ends_at = item.get("ends_at")
        row.registration_status = item["registration_status"]
        row.event_status = item["event_status"]
        row.format = item.get("format")
        row.location = item.get("location")
        row.tags = item.get("tags")
        row.prize_text = item.get("prize_text")
        row.organizer = item.get("organizer")
        row.image_url = item.get("image_url")
        row.last_seen_at = now
        row.check_error = None
        row.is_new = compute_is_new(
            event_status=row.event_status,
            registration_status=row.registration_status,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            now=now,
        )
        updated += 1

    for key, item in by_key.items():
        if key in seen:
            continue
        session.add(
            HackathonEvent(
                source=item["source"],
                source_id=item["source_id"],
                title=item["title"],
                url=item["url"],
                description=item.get("description"),
                starts_at=item.get("starts_at"),
                ends_at=item.get("ends_at"),
                registration_status=item["registration_status"],
                event_status=item["event_status"],
                format=item.get("format"),
                location=item.get("location"),
                tags=item.get("tags"),
                prize_text=item.get("prize_text"),
                organizer=item.get("organizer"),
                image_url=item.get("image_url"),
                first_seen_at=now,
                last_seen_at=now,
                check_error=None,
                is_new=compute_is_new(
                    event_status=item["event_status"],
                    registration_status=item["registration_status"],
                    starts_at=item.get("starts_at"),
                    ends_at=item.get("ends_at"),
                    now=now,
                ),
            )
        )
        created += 1

    if errors:
        # stash last sync error on a synthetic marker? skip — API shows empty with message
        pass
    await session.commit()
    return {"created": created, "updated": updated, "errors": len(errors), "total": len(by_key)}
