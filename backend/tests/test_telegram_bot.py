from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models.telegram_bot import TelegramBotBind, TelegramLinkToken
from app.services import telegram_bot as bot
from app.services.telegram_notify import format_digest, format_step_nudge, ping_line


def test_digest_silent_when_empty() -> None:
    assert format_digest(vacancies=[], internships=[], hackathons=[], pings=[], steps=[]) is None


def test_digest_and_ping_include_alias_not_spam() -> None:
    vacancy = SimpleNamespace(company="Avito", title="Go backend", telegram_alias="@hravito")
    text = format_digest(
        vacancies=[vacancy],
        internships=["Яндекс"],
        hackathons=[("AI Cup", "https://example.com/ai")],
        pings=[(vacancy, 6)],
        steps=[],
        origin="https://hunt.example",
    )
    assert text is not None
    assert "Inbox · 1 новых" in text
    assert "Avito — Go backend" in text
    assert "Стажировки открылись" in text
    assert "Хакатоны" in text
    assert "@hravito" in text
    assert "https://t.me/hravito" in ping_line(vacancy, 6)
    assert "https://hunt.example" in text


def test_step_nudge_is_short() -> None:
    event = SimpleNamespace(kind="screening", label=None)
    vacancy = SimpleNamespace(company="Яндекс", title="Python")
    text = format_step_nudge([(event, vacancy, "12:00")])
    assert text == "Скоро\n12:00 · скрининг · Яндекс — Python"


def _session(resp) -> dict[str, str]:
    token = resp.cookies.get("hunt_session")
    assert token, resp.text
    return {"hunt_session": token}


def _register(client: TestClient, email: str) -> tuple[dict, dict[str, str]]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return resp.json(), _session(resp)


def test_bot_is_personal_and_hidden_from_guest_token(client: TestClient, test_db_path) -> None:
    suffix = uuid4().hex[:8]
    host, host_c = _register(client, f"host-{suffix}@hunt.test")
    if not host.get("is_host"):
        import sqlite3

        con = sqlite3.connect(test_db_path)
        con.execute("UPDATE users SET is_host = 0")
        con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (host["id"],))
        con.commit()
        con.close()
    guest, guest_c = _register(client, f"guest-{suffix}@hunt.test")

    status = client.get("/api/telegram/bot", cookies=guest_c)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["connected"] is False
    assert "host" not in str(body).lower()
    assert client.put("/api/telegram/bot/token", json={"token": "x"}, cookies=guest_c).status_code == 404
    assert client.post("/api/telegram/bot/link", cookies=guest_c).status_code == 400

    prefs = client.put(
        "/api/telegram/bot/prefs",
        json={"want_vacancies": False, "want_ping": True},
        cookies=guest_c,
    )
    assert prefs.status_code == 200, prefs.text
    assert prefs.json()["want_vacancies"] is False
    assert prefs.json()["want_ping"] is True
    del host_c


def test_guest_gets_personal_start_link_when_bot_is_configured(client: TestClient, monkeypatch) -> None:
    async def fake_me(_token: str) -> dict:
        return {"id": 1, "username": "huntos_notify_bot"}

    monkeypatch.setattr(bot, "fetch_me", fake_me)
    monkeypatch.setattr(bot.settings, "telegram_bot_token", "123456:test-token")
    suffix = uuid4().hex[:8]
    _register(client, f"host-{suffix}@hunt.test")
    _guest, guest_c = _register(client, f"guest-{suffix}@hunt.test")

    status = client.get("/api/telegram/bot", cookies=guest_c)
    assert status.status_code == 200, status.text
    assert status.json()["available"] is True
    assert client.put("/api/telegram/bot/token", json={"token": "nope"}, cookies=guest_c).status_code == 404

    linked = client.post("/api/telegram/bot/link", cookies=guest_c)
    assert linked.status_code == 200, linked.text
    url = linked.json()["url"]
    assert url.startswith("https://t.me/huntos_notify_bot?start=")
    code = url.rsplit("start=", 1)[-1]
    assert len(code) >= 8

    async def _start() -> str | None:
        async with SessionLocal() as session:
            return await bot.handle_message(
                session,
                {
                    "text": f"/start {code}",
                    "chat": {"id": 4242},
                    "from": {"id": 8800555, "username": "guest_tg"},
                },
            )

    reply = asyncio.run(_start())
    assert reply and "Готово" in reply
    me = client.get("/api/telegram/bot", cookies=guest_c).json()
    assert me["connected"] is True
    assert me["telegram_username"] == "guest_tg"


def test_one_telegram_cannot_bind_two_hunt_users(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    first, first_c = _register(client, f"a-{suffix}@hunt.test")
    second, _second_c = _register(client, f"b-{suffix}@hunt.test")

    async def _seed() -> None:
        async with SessionLocal() as session:
            now = datetime.now(UTC).replace(tzinfo=None)
            session.add(TelegramLinkToken(token="tok-a", user_id=first["id"], expires_at=now + timedelta(hours=1)))
            session.add(TelegramLinkToken(token="tok-b", user_id=second["id"], expires_at=now + timedelta(hours=1)))
            await session.commit()
            msg_a = await bot.handle_message(
                session,
                {
                    "text": "/start tok-a",
                    "chat": {"id": 111},
                    "from": {"id": 999001, "username": "one"},
                },
            )
            assert msg_a and "Готово" in msg_a
            msg_b = await bot.handle_message(
                session,
                {
                    "text": "/start tok-b",
                    "chat": {"id": 222},
                    "from": {"id": 999001, "username": "one"},
                },
            )
            assert msg_b and "другому аккаунту" in msg_b
            rows = (await session.execute(select(TelegramBotBind))).scalars().all()
            owners = {
                row.user_id: row.telegram_user_id
                for row in rows
                if row.telegram_user_id and row.user_id in {first["id"], second["id"]}
            }
            assert owners == {first["id"]: 999001}

    asyncio.run(_seed())
    me = client.get("/api/telegram/bot", cookies=first_c).json()
    assert me["connected"] is True
    assert me["telegram_username"] == "one"
