from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.models.scrape_queue import ScrapeQueueItem
from app.models.scraper_config import ScraperConfig
from app.services.scraper.query_key import make_query_key


def _session(resp) -> dict[str, str]:
    token = resp.cookies.get("hunt_session")
    assert token, resp.text
    return {"hunt_session": token}


def _register(client: TestClient, email: str) -> tuple[dict, dict[str, str]]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return resp.json(), _session(resp)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


SEARCH = {
    "name": "ML remote",
    "source": "hirehi",
    "enabled": True,
    "interval_minutes": 15,
    "max_pages": 1,
    "query_params": {"search": "ML", "format": ["удалённо"], "category": "development"},
}


def test_query_key_ignores_headed_sort_and_case() -> None:
    a = make_query_key("hh", {"search": "Go", "area": ["1"], "headed": True, "order_by": "salary_desc"})
    b = make_query_key("hh", {"search": "go", "area": ["1"], "headed": False, "order_by": "publication_time"})
    assert a == b
    hire_a = make_query_key("hirehi", {"search": "QA", "sort": "salary_desc"})
    hire_b = make_query_key("hirehi", {"search": "qa", "sort": "date"})
    assert hire_a == hire_b
    assert a != hire_a
    typed_go = make_query_key("hirehi", {"search": "golang", "category": "development"})
    chip_go = make_query_key("hirehi", {"subcategory": ["go"], "category": "development"})
    assert typed_go == chip_go


def test_interval_clamped_to_global_min(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    resp = client.post("/api/scraper-configs", json=SEARCH, cookies=cookies)
    assert resp.status_code == 200, resp.text
    assert resp.json()["interval_minutes"] == 30


def test_queue_dedupes_same_query(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    first = client.post("/api/scraper-configs", json=SEARCH, cookies=cookies)
    second = client.post(
        "/api/scraper-configs",
        json={**SEARCH, "name": "same filters"},
        cookies=cookies,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    from app.db import SessionLocal
    from app.services.scraper.queue import enqueue_query

    async def go() -> int:
        async with SessionLocal() as session:
            cfg = await session.get(ScraperConfig, first.json()["id"])
            other = await session.get(ScraperConfig, second.json()["id"])
            assert cfg is not None and other is not None
            one = await enqueue_query(session, config=cfg)
            two = await enqueue_query(session, config=other)
            assert one.id == two.id
            pending = (
                await session.execute(
                    select(ScrapeQueueItem).where(
                        ScrapeQueueItem.status == "pending",
                        ScrapeQueueItem.query_key == one.query_key,
                    )
                )
            ).scalars().all()
            return len(pending)

    assert _run(go()) == 1


def test_config_cap(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    from app.config import settings

    monkeypatch.setattr(settings, "scraper_max_configs_per_user", 1)
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    ok = client.post("/api/scraper-configs", json=SEARCH, cookies=cookies)
    assert ok.status_code == 200, ok.text
    denied = client.post(
        "/api/scraper-configs",
        json={**SEARCH, "name": "second", "query_params": {"search": "java"}},
        cookies=cookies,
    )
    assert denied.status_code == 400


def test_all_career_boards_fit_under_default_cap(client: TestClient) -> None:
    from app.services.scraper.sources.career_catalog import BOARDS

    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    for board in BOARDS:
        resp = client.post(
            "/api/scraper-configs",
            json={
                "name": board.name,
                "source": "career",
                "enabled": True,
                "query_params": {"company": board.slug, "stack": ["go"]},
            },
            cookies=cookies,
        )
        assert resp.status_code == 200, resp.text
    listed = client.get("/api/scraper-configs", cookies=cookies)
    assert listed.status_code == 200
    enabled = [row for row in listed.json() if row["enabled"]]
    assert {row["query_params"]["company"] for row in enabled} == {board.slug for board in BOARDS}


def test_disabled_search_frees_cap_slot(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    from app.config import settings

    monkeypatch.setattr(settings, "scraper_max_configs_per_user", 1)
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    first = client.post("/api/scraper-configs", json=SEARCH, cookies=cookies)
    assert first.status_code == 200, first.text
    off = client.put(
        f"/api/scraper-configs/{first.json()['id']}",
        json={**SEARCH, "enabled": False},
        cookies=cookies,
    )
    assert off.status_code == 200, off.text
    assert off.json()["enabled"] is False
    second = client.post(
        "/api/scraper-configs",
        json={**SEARCH, "name": "second", "query_params": {"search": "java"}},
        cookies=cookies,
    )
    assert second.status_code == 200, second.text


def test_delete_search_with_vacancies(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    from app.services.scraper.engine import SOURCES

    class FakeHireHi:
        def __init__(self, http=None) -> None:
            pass

        async def search(self, query_params, *, page: int, limit: int = 20) -> dict:
            return {"jobs": [{"id": "99", "title": "ML engineer"}], "has_more": False}

        async def detail(self, job_id, query_params=None) -> dict:
            return {"id": str(job_id), "title": "ML engineer", "company": "Acme", "description": "Need Python ML"}

        def normalize(self, detail: dict, listing_item=None) -> dict:
            return {
                "source": "hirehi",
                "source_id": str(detail.get("id") or "99"),
                "title": detail.get("title") or "ML engineer",
                "company": detail.get("company") or "Acme",
                "description": detail.get("description") or "Need Python ML",
                "requirements": detail.get("description") or "Need Python ML",
            }

    monkeypatch.setitem(SOURCES, "hirehi", FakeHireHi)
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    created = client.post("/api/scraper-configs", json=SEARCH, cookies=cookies)
    assert created.status_code == 200, created.text
    config_id = created.json()["id"]

    from app.db import SessionLocal
    from app.services.scraper.engine import run_config

    async def go() -> None:
        async with SessionLocal() as session:
            cfg = await session.get(ScraperConfig, config_id)
            assert cfg is not None
            await run_config(session, cfg)

    _run(go())
    vacancies = client.get("/api/vacancies", cookies=cookies)
    assert vacancies.status_code == 200
    assert any(row["source_id"] == "99" for row in vacancies.json()["items"])
    deleted = client.delete(f"/api/scraper-configs/{config_id}", cookies=cookies)
    assert deleted.status_code == 200, deleted.text
    left = client.get("/api/scraper-configs", cookies=cookies)
    assert left.json() == []
    still = client.get("/api/vacancies", cookies=cookies)
    assert any(row["source_id"] == "99" for row in still.json()["items"])


def test_run_now_marks_queue_force(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _, cookies = _register(client, f"u-{suffix}@hunt.test")
    created = client.post("/api/scraper-configs", json=SEARCH, cookies=cookies)
    assert created.status_code == 200, created.text
    config_id = created.json()["id"]
    query_key = created.json().get("query_key")
    kicked = client.post(f"/api/scraper/run/{config_id}", cookies=cookies)
    assert kicked.status_code == 200, kicked.text

    from app.db import SessionLocal
    from app.services.scraper.engine import query_key_for

    async def go() -> bool:
        async with SessionLocal() as session:
            cfg = await session.get(ScraperConfig, config_id)
            assert cfg is not None
            key = query_key or query_key_for(cfg)
            row = (
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
            assert row is not None
            return bool(row.force)

    assert _run(go()) is True


def test_hh_crawl_pages_are_not_capped_at_three() -> None:
    from types import SimpleNamespace

    from app.services.scraper.engine import crawl_max_pages

    siblings = [SimpleNamespace(max_pages=3)]
    assert crawl_max_pages("hh", siblings) == 40
    assert crawl_max_pages("habr", [SimpleNamespace(max_pages=1)]) == 40
    assert crawl_max_pages("geekjob", [SimpleNamespace(max_pages=1)]) == 40
    assert crawl_max_pages("getmatch", [SimpleNamespace(max_pages=3)]) == 20
    assert crawl_max_pages("hirehi", [SimpleNamespace(max_pages=1)]) == 5


def test_claim_next_skips_source_at_capacity(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    from datetime import UTC, datetime

    from app.config import settings
    from app.db import SessionLocal
    from app.models.scrape_queue import ScrapeQueueItem
    from app.services.scraper.queue import claim_next

    del client
    monkeypatch.setattr(settings, "scraper_hirehi_concurrency", 1)
    now = datetime.now(UTC).replace(tzinfo=None)

    async def go() -> str | None:
        async with SessionLocal() as session:
            await session.execute(delete(ScrapeQueueItem))
            await session.commit()
            session.add_all(
                [
                    ScrapeQueueItem(
                        query_key="hirehi:busy",
                        source="hirehi",
                        status="running",
                        queued_at=now,
                        started_at=now,
                        requested_config_ids=[],
                    ),
                    ScrapeQueueItem(
                        query_key="hirehi:wait",
                        source="hirehi",
                        status="pending",
                        queued_at=now,
                        requested_config_ids=[],
                    ),
                    ScrapeQueueItem(
                        query_key="habr:go",
                        source="habr",
                        status="pending",
                        queued_at=now,
                        requested_config_ids=[],
                    ),
                ]
            )
            await session.commit()
            claimed = await claim_next(session)
            return claimed.source if claimed else None

    assert _run(go()) == "habr"


def test_claim_next_skips_second_browser_source(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    from datetime import UTC, datetime

    from app.config import settings
    from app.db import SessionLocal
    from app.models.scrape_queue import ScrapeQueueItem
    from app.services.scraper.queue import claim_next

    del client
    monkeypatch.setattr(settings, "scraper_browser_concurrency", 1)
    now = datetime.now(UTC).replace(tzinfo=None)

    async def go() -> str | None:
        async with SessionLocal() as session:
            await session.execute(delete(ScrapeQueueItem))
            await session.commit()
            session.add_all(
                [
                    ScrapeQueueItem(
                        query_key="hh:busy",
                        source="hh",
                        status="running",
                        queued_at=now,
                        started_at=now,
                        requested_config_ids=[],
                    ),
                    ScrapeQueueItem(
                        query_key="getmatch:wait",
                        source="getmatch",
                        status="pending",
                        queued_at=now,
                        requested_config_ids=[],
                    ),
                    ScrapeQueueItem(
                        query_key="career:go",
                        source="career",
                        status="pending",
                        queued_at=now,
                        requested_config_ids=[],
                    ),
                ]
            )
            await session.commit()
            claimed = await claim_next(session)
            return claimed.source if claimed else None

    assert _run(go()) == "career"


def test_polite_http_delays_per_host_not_process_wide(monkeypatch) -> None:  # noqa: ANN001
    import time

    from app.config import settings
    from app.services.scraper.http import PoliteHttp, reset_http_clock

    monkeypatch.setattr(settings, "scraper_min_delay_sec", 0.08)
    monkeypatch.setattr(settings, "scraper_max_delay_sec", 0.08)
    reset_http_clock()
    client = PoliteHttp()

    async def go() -> float:
        await asyncio.gather(
            client._sleep("https://hirehi.ru/a"),
            client._sleep("https://career.habr.com/a"),
        )
        started = time.monotonic()
        await asyncio.gather(
            client._sleep("https://hirehi.ru/b"),
            client._sleep("https://career.habr.com/b"),
        )
        return time.monotonic() - started

    elapsed = _run(go())
    assert 0.06 <= elapsed < 0.14
