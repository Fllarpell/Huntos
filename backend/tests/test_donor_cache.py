from __future__ import annotations

import asyncio
from uuid import uuid4

from app.db import SessionLocal
from app.models.scraper_config import ScraperConfig
from app.services.scraper.engine import SOURCES, run_config


class FakeHireHi:
    search_calls = 0

    def __init__(self, http=None) -> None:
        pass

    async def search(self, query_params, *, page: int, limit: int = 20) -> dict:
        type(self).search_calls += 1
        return {"jobs": [{"id": "42", "title": "Go backend"}], "has_more": False}

    async def detail(self, job_id, query_params=None) -> dict:
        return {
            "id": str(job_id),
            "title": "Go backend",
            "company": "Acme",
            "description": "Need Go",
        }

    def normalize(self, detail: dict, listing_item=None) -> dict:
        return {
            "source": "hirehi",
            "source_id": str(detail.get("id") or "42"),
            "title": detail.get("title") or "Go backend",
            "company": detail.get("company") or "Acme",
            "description": detail.get("description") or "Need Go",
            "requirements": detail.get("description") or "Need Go",
        }


def _register(client, email: str) -> dict[str, str]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return {"hunt_session": resp.cookies["hunt_session"]}


def _search_payload() -> dict:
    return {
        "name": "Go",
        "source": "hirehi",
        "enabled": True,
        "query_params": {"search": "Go", "category": "development"},
        "interval_minutes": 60,
        "max_pages": 1,
    }


def test_guest_search_uses_host_cache_not_donor(client, monkeypatch) -> None:
    FakeHireHi.search_calls = 0
    monkeypatch.setitem(SOURCES, "hirehi", FakeHireHi)
    suffix = uuid4().hex[:8]
    host_c = _register(client, f"host-{suffix}@hunt.test")
    guest_c = _register(client, f"guest-{suffix}@hunt.test")

    host_cfg = client.post("/api/scraper-configs", json=_search_payload(), cookies=host_c)
    guest_cfg = client.post("/api/scraper-configs", json=_search_payload(), cookies=guest_c)
    assert host_cfg.status_code == 200, host_cfg.text
    assert guest_cfg.status_code == 200, guest_cfg.text

    async def _run() -> None:
        async with SessionLocal() as session:
            host_row = await session.get(ScraperConfig, host_cfg.json()["id"])
            guest_row = await session.get(ScraperConfig, guest_cfg.json()["id"])
            assert host_row and guest_row
            await run_config(session, host_row)
            await run_config(session, guest_row)

    asyncio.run(_run())
    assert FakeHireHi.search_calls == 1


def test_force_recrawl_hits_donor_again(client, monkeypatch) -> None:
    FakeHireHi.search_calls = 0
    monkeypatch.setitem(SOURCES, "hirehi", FakeHireHi)
    suffix = uuid4().hex[:8]
    host_c = _register(client, f"host-{suffix}@hunt.test")
    payload = {
        **_search_payload(),
        "name": f"Force {suffix}",
        "query_params": {"search": f"Force{suffix}", "category": "development"},
    }
    cfg = client.post("/api/scraper-configs", json=payload, cookies=host_c)
    assert cfg.status_code == 200, cfg.text

    async def _run(force: bool) -> None:
        async with SessionLocal() as session:
            row = await session.get(ScraperConfig, cfg.json()["id"])
            assert row
            await run_config(session, row, force=force)

    asyncio.run(_run(False))
    first = FakeHireHi.search_calls
    assert first >= 1
    asyncio.run(_run(False))
    assert FakeHireHi.search_calls == first
    asyncio.run(_run(True))
    assert FakeHireHi.search_calls > first


def _promote_host(client, cookies, test_db_path) -> None:
    me = client.get("/api/auth/me", cookies=cookies).json()
    if me.get("is_host"):
        return
    import sqlite3

    con = sqlite3.connect(test_db_path)
    con.execute("UPDATE users SET is_host = 0")
    con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (me["id"],))
    con.commit()
    con.close()


def test_guest_unique_search_enqueues_host_crawl_without_host_config(
    client, monkeypatch, test_db_path
) -> None:
    FakeHireHi.search_calls = 0
    monkeypatch.setitem(SOURCES, "hirehi", FakeHireHi)
    suffix = uuid4().hex[:8]
    host_c = _register(client, f"host-{suffix}@hunt.test")
    _promote_host(client, host_c, test_db_path)
    guest_c = _register(client, f"guest-{suffix}@hunt.test")

    class FakeQA(FakeHireHi):
        async def search(self, query_params, *, page: int, limit: int = 20) -> dict:
            type(self).search_calls += 1
            return {"jobs": [{"id": "77", "title": "QA automation"}], "has_more": False}

        async def detail(self, job_id, query_params=None) -> dict:
            return {
                "id": str(job_id),
                "title": "QA automation",
                "company": "Acme",
                "description": "Need pytest",
            }

        def normalize(self, detail: dict, listing_item=None) -> dict:
            return {
                "source": "hirehi",
                "source_id": str(detail.get("id") or "77"),
                "title": detail.get("title") or "QA automation",
                "company": detail.get("company") or "Acme",
                "description": detail.get("description") or "Need pytest",
                "requirements": detail.get("description") or "Need pytest",
            }

    monkeypatch.setitem(SOURCES, "hirehi", FakeQA)
    FakeQA.search_calls = 0

    host_cfg = client.post("/api/scraper-configs", json=_search_payload(), cookies=host_c)
    assert host_cfg.status_code == 200, host_cfg.text
    guest_cfg = client.post(
        "/api/scraper-configs",
        json={
            "name": "QA other",
            "source": "hirehi",
            "enabled": True,
            "query_params": {"search": "QA", "category": "qa", "format": ["удалённо"]},
            "interval_minutes": 60,
            "max_pages": 1,
        },
        cookies=guest_c,
    )
    assert guest_cfg.status_code == 200, guest_cfg.text
    assert guest_cfg.json()["last_run"]["status"] == "queued"

    guest_crawls = client.get("/api/scraper/crawls", cookies=guest_c)
    assert guest_crawls.status_code == 404
    crawls = client.get("/api/scraper/crawls", cookies=host_c)
    assert crawls.status_code == 200, crawls.text
    assert all(row["subscribers"] == [] for row in crawls.json())
    names = {row["name"] for row in crawls.json()}
    assert any("QA" in name for name in names)
    qa = next(row for row in crawls.json() if "QA" in row["name"] or row["query_params"].get("search") == "QA")
    assert qa["host_subscribed"] is False
    assert qa["queue_status"] == "pending"
    assert qa["last_fetched_at"] is None

    host_own = client.get("/api/scraper-configs", cookies=host_c)
    assert all(row["query_params"].get("search") != "QA" for row in host_own.json())

    async def _run() -> None:
        async with SessionLocal() as session:
            guest_row = await session.get(ScraperConfig, guest_cfg.json()["id"])
            assert guest_row
            await run_config(session, guest_row)

    asyncio.run(_run())
    assert FakeQA.search_calls >= 1

    guest_list = client.get("/api/vacancies", cookies=guest_c)
    host_list = client.get("/api/vacancies", cookies=host_c)
    guest_ids = {row["source_id"] for row in guest_list.json()["items"] if row["source"] == "hirehi"}
    host_ids = {row["source_id"] for row in host_list.json()["items"] if row["source"] == "hirehi"}
    assert "77" in guest_ids
    assert "77" not in host_ids


def test_typed_go_reuses_go_chip_cache(client, monkeypatch) -> None:
    FakeHireHi.search_calls = 0
    monkeypatch.setitem(SOURCES, "hirehi", FakeHireHi)
    suffix = uuid4().hex[:8]
    host_c = _register(client, f"host-{suffix}@hunt.test")
    guest_c = _register(client, f"guest-{suffix}@hunt.test")

    host_cfg = client.post(
        "/api/scraper-configs",
        json={
            "name": "Go chip",
            "source": "hirehi",
            "enabled": True,
            "query_params": {"subcategory": ["go"], "category": "development"},
            "interval_minutes": 60,
            "max_pages": 1,
        },
        cookies=host_c,
    )
    assert host_cfg.status_code == 200, host_cfg.text

    async def _host() -> None:
        async with SessionLocal() as session:
            row = await session.get(ScraperConfig, host_cfg.json()["id"])
            assert row
            await run_config(session, row)

    asyncio.run(_host())
    after_host = FakeHireHi.search_calls

    guest_cfg = client.post(
        "/api/scraper-configs",
        json={
            "name": "go text",
            "source": "hirehi",
            "enabled": True,
            "query_params": {"search": "golang", "category": "development"},
            "interval_minutes": 60,
            "max_pages": 1,
        },
        cookies=guest_c,
    )
    assert guest_cfg.status_code == 200, guest_cfg.text
    assert guest_cfg.json()["last_run"]["status"] == "ok"
    assert FakeHireHi.search_calls == after_host
    guest_list = client.get("/api/vacancies", cookies=guest_c)
    assert any(row["source_id"] == "42" for row in guest_list.json()["items"])


def test_go_search_copies_from_wide_it_cache(client, monkeypatch) -> None:
    FakeHireHi.search_calls = 0
    monkeypatch.setitem(SOURCES, "hirehi", FakeHireHi)
    suffix = uuid4().hex[:8]
    host_c = _register(client, f"host-{suffix}@hunt.test")
    guest_c = _register(client, f"guest-{suffix}@hunt.test")

    host_wide = client.post(
        "/api/scraper-configs",
        json={
            "name": "весь IT",
            "source": "hirehi",
            "enabled": True,
            "query_params": {"search": "", "category": "development"},
            "interval_minutes": 60,
            "max_pages": 1,
        },
        cookies=host_c,
    )
    assert host_wide.status_code == 200, host_wide.text

    async def _host() -> None:
        async with SessionLocal() as session:
            row = await session.get(ScraperConfig, host_wide.json()["id"])
            assert row
            await run_config(session, row)

    asyncio.run(_host())
    after_host = FakeHireHi.search_calls

    guest_cfg = client.post(
        "/api/scraper-configs",
        json={
            "name": "only go",
            "source": "hirehi",
            "enabled": True,
            "query_params": {"search": "go", "category": "development"},
            "interval_minutes": 60,
            "max_pages": 1,
        },
        cookies=guest_c,
    )
    assert guest_cfg.status_code == 200, guest_cfg.text
    assert guest_cfg.json()["last_run"]["status"] == "ok"
    assert FakeHireHi.search_calls == after_host
    items = client.get("/api/vacancies", cookies=guest_c).json()["items"]
    assert any(row["source_id"] == "42" for row in items)
