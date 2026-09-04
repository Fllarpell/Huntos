import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_migrate import apply_schema
from app.models.internship_monitor import InternshipMonitor
from app.services.internship_catalog import program_by_slug
from app.services.internship_monitor import detect_live_status, refresh_internship_statuses


def test_detect_live_status_keywords() -> None:
    open_html = "<html><body><h1>Стажировка</h1><button>Подать заявку</button></body></html>"
    closed_html = "<html><body><p>Набор закрыт до осени</p></body></html>"
    waiting_html = "<html><body><p>Следите за анонсом следующего набора</p></body></html>"

    assert detect_live_status(open_html)[0] == "open"
    assert detect_live_status(closed_html)[0] == "closed"
    assert detect_live_status(waiting_html)[0] == "waiting"


def test_refresh_skips_recent_checks() -> None:
    async def _run() -> None:
        await apply_schema()
        async with SessionLocal() as session:
            program = program_by_slug("yandex-intern")
            assert program is not None
            session.add(
                InternshipMonitor(
                    program_slug=program.slug,
                    live_status="open",
                    checked_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            await session.commit()
            with (
                patch("app.services.internship_monitor.PROGRAMS", (program,)),
                patch("app.services.internship_monitor.PoliteHttp") as http_cls,
            ):
                updated = await refresh_internship_statuses(session)
            assert updated == 0
            http_cls.assert_not_called()

    asyncio.run(_run())


def test_refresh_updates_stale_program() -> None:
    async def _run() -> None:
        await apply_schema()
        async with SessionLocal() as session:
            program = program_by_slug("avito-start")
            assert program is not None
            session.add(
                InternshipMonitor(
                    program_slug=program.slug,
                    live_status="closed",
                    checked_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
                )
            )
            await session.commit()

            http = AsyncMock()
            http.get_text = AsyncMock(return_value="<html><a>Подать заявку</a></html>")

            with (
                patch("app.services.internship_monitor.PROGRAMS", (program,)),
                patch("app.services.internship_monitor.PoliteHttp", return_value=http),
            ):
                updated = await refresh_internship_statuses(session, force=False)
            assert updated == 1

            row = await session.get(InternshipMonitor, program.slug)
            assert row is not None
            assert row.live_status == "open"

    asyncio.run(_run())


def test_internships_api_includes_live_fields(client: TestClient) -> None:
    email = f"intern-{uuid4().hex[:8]}@hunt.test"
    cookies = client.post("/api/auth/register", json={"email": email, "password": "password1"}).cookies
    listed = client.get("/api/internships?kind=internship", cookies=cookies)
    assert listed.status_code == 200
    row = listed.json()[0]
    assert row["live_status"] in {None, "open", "waiting", "closed", "monitor"}
    assert "checked_at" in row
    assert row["catalog_status"] in {"open", "waiting", "closed", "monitor"}
