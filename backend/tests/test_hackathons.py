from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.hackathons_parse import parse_ods_fixture, parse_tilda_feed
from app.services.hackathons_sync import compute_is_new


def test_finished_hackathon_is_not_new() -> None:
    now = datetime(2026, 9, 4, 12, 0, 0)
    assert not compute_is_new(
        event_status="finished",
        registration_status="open",
        now=now,
    )
    assert not compute_is_new(
        event_status="upcoming",
        registration_status="closed",
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=1),
        now=now,
    )


def test_open_or_running_hackathon_is_new() -> None:
    now = datetime(2026, 9, 4, 12, 0, 0)
    assert compute_is_new(event_status="upcoming", registration_status="open", now=now)
    assert compute_is_new(event_status="active", registration_status="closed", now=now)
    assert compute_is_new(
        event_status="unknown",
        registration_status="unknown",
        starts_at=now - timedelta(hours=2),
        ends_at=now + timedelta(hours=2),
        now=now,
    )
    assert not compute_is_new(event_status="upcoming", registration_status="closed", now=now)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_hackrus_feed_marks_registration_open() -> None:
    payload = json.loads((FIXTURES / "hackrus_feed.json").read_text())
    events = parse_tilda_feed(payload, source="hackrus", default_event_status="upcoming")
    assert events
    assert events[0]["source"] == "hackrus"
    assert events[0]["title"]
    assert events[0]["url"].startswith("http")
    assert events[0]["registration_status"] in {"open", "closed", "unknown"}
    assert events[0]["image_url"] and events[0]["image_url"].startswith("http")
    assert events[0]["prize_text"] and "₽" in events[0]["prize_text"]


def test_parse_hackathons_pro_feed() -> None:
    payload = json.loads((FIXTURES / "hackathons_pro_feed.json").read_text())
    events = parse_tilda_feed(payload, source="hackathons_pro", default_event_status="active")
    assert events
    assert events[0]["source"] == "hackathons_pro"
    assert "хакатон" in events[0]["title"].casefold() or events[0]["title"]
    assert events[0]["prize_text"]
    assert events[0]["image_url"]
    inter_rao = next(item for item in events if "Интер" in item["title"])
    assert inter_rao["organizer"] and "Интер" in inter_rao["organizer"]


def test_parse_ods_fixture_active_and_past() -> None:
    payload = json.loads((FIXTURES / "ods_competitions.json").read_text())
    events = parse_ods_fixture(payload)
    assert any(item["event_status"] == "active" for item in events) or any(
        item["event_status"] == "upcoming" for item in events
    )
    assert any(item["event_status"] == "finished" for item in events)
    assert all(item["source"] == "ods" for item in events)


def test_hackathons_api_list_and_track(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"hack-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}

    # Seed one event via sync may hit network; insert through parse upsert by posting sync
    # with patched collect is heavy — create row through DB by syncing fixtures in-process.
    from app.db import SessionLocal
    from app.models.hackathon_event import HackathonEvent
    import asyncio

    async def seed() -> int:
        async with SessionLocal() as session:
            now = datetime.now(UTC).replace(tzinfo=None)
            row = HackathonEvent(
                source="hackrus",
                source_id=f"test-{suffix}",
                title="Тестовый хакатон",
                url="https://example.com/hack",
                description="регистрация открыта",
                registration_status="open",
                event_status="upcoming",
                format="online",
                location="Москва",
                tags="Регистрация открыта,online",
                first_seen_at=now,
                last_seen_at=now,
                is_new=True,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row.id

    event_id = asyncio.run(seed())

    listed = client.get("/api/hackathons", cookies=cookies)
    assert listed.status_code == 200
    rows = listed.json()
    live = next(item for item in rows if item["id"] == event_id)
    assert live["is_new"] is True

    async def seed_finished() -> int:
        async with SessionLocal() as session:
            now = datetime.now(UTC).replace(tzinfo=None)
            row = HackathonEvent(
                source="hackrus",
                source_id=f"past-{suffix}",
                title="Прошедший хакатон",
                url="https://example.com/past",
                registration_status="closed",
                event_status="finished",
                first_seen_at=now,
                last_seen_at=now,
                is_new=True,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row.id

    past_id = asyncio.run(seed_finished())
    listed = client.get("/api/hackathons", cookies=cookies)
    past = next(item for item in listed.json() if item["id"] == past_id)
    assert past["is_new"] is False

    saved = client.put(
        f"/api/hackathons/{event_id}",
        json={"status": "watch", "notes": "хочу в команду"},
        cookies=cookies,
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["track"]["status"] == "watch"
    assert body["track"]["notes"] == "хочу в команду"
