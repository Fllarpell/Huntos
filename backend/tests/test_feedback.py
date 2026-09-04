from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.models.telegram_bot import TelegramBotBind
from app.services.feedback_notify import format_feedback_message, parse_chat_id


def _session(resp) -> dict[str, str]:
    token = resp.cookies.get("hunt_session")
    assert token, resp.text
    return {"hunt_session": token}


def _register(client: TestClient, email: str) -> tuple[dict, dict[str, str]]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return resp.json(), _session(resp)


def test_format_feedback_message_includes_optional_fields() -> None:
    text = format_feedback_message(
        kind="bug",
        body="Inbox не открывает карточку",
        email="guest@hunt.test",
        page="/",
        contact_name="Дима",
        reply_to="@dima",
    )
    assert text.startswith("ошибка")
    assert "guest@hunt.test" in text
    assert "экран Inbox" in text
    assert "кто Дима" in text
    assert "ответ @dima" in text
    assert "Inbox не открывает карточку" in text
    assert parse_chat_id(" 42 ") == 42
    assert parse_chat_id("") is None


def test_guest_can_send_feedback_host_reads_it(client: TestClient, test_db_path) -> None:
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

    too_short = client.post(
        "/api/feedback",
        json={"kind": "bug", "body": "коротко"},
        cookies=guest_c,
    )
    assert too_short.status_code == 422 or too_short.status_code == 400

    sent = client.post(
        "/api/feedback",
        json={
            "kind": "bug",
            "body": "Inbox не открывает карточку после обновления",
            "page": "/",
            "contact_name": "Дима",
            "reply_to": "@dima",
        },
        cookies=guest_c,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["ok"] is True

    idea = client.post(
        "/api/feedback",
        json={"kind": "idea", "body": "Хочу фильтр по зарплате на воронке"},
        cookies=guest_c,
    )
    assert idea.status_code == 200, idea.text

    assert client.get("/api/feedback", cookies=guest_c).status_code == 404

    inbox = client.get("/api/feedback", cookies=host_c)
    assert inbox.status_code == 200, inbox.text
    rows = inbox.json()
    bodies = {row["body"] for row in rows}
    emails = {row["email"] for row in rows}
    kinds = {row["kind"] for row in rows}
    assert "Inbox не открывает карточку после обновления" in bodies
    assert "Хочу фильтр по зарплате на воронке" in bodies
    assert guest["email"] in emails
    assert kinds >= {"bug", "idea"}
    bug = next(row for row in rows if row["kind"] == "bug")
    assert bug["page"] == "/"
    assert bug["contact_name"] == "Дима"
    assert bug["reply_to"] == "@dima"
    assert all("is_host" not in row and "can_observe" not in row for row in rows)


def test_feedback_notifies_telegram_and_email(client: TestClient, test_db_path, monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    host, host_c = _register(client, f"host-{suffix}@hunt.test")
    if not host.get("is_host"):
        import sqlite3

        con = sqlite3.connect(test_db_path)
        con.execute("UPDATE users SET is_host = 0")
        con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (host["id"],))
        con.commit()
        con.close()
    _guest, guest_c = _register(client, f"guest-{suffix}@hunt.test")

    sent_tg: list[tuple] = []
    sent_mail: list[tuple[str, str]] = []

    async def fake_send(token: str, chat_id: int, text: str) -> bool:
        sent_tg.append((token, chat_id, text))
        return True

    monkeypatch.setattr("app.services.feedback_notify.send_text", fake_send)
    monkeypatch.setattr(
        "app.services.feedback_notify.send_smtp",
        lambda subject, body: sent_mail.append((subject, body)) or True,
    )
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example")
    monkeypatch.setattr(settings, "smtp_user", "me@example.com")
    monkeypatch.setattr(settings, "feedback_email_to", "me@example.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")

    async def _bind() -> None:
        async with SessionLocal() as session:
            session.add(
                TelegramBotBind(
                    user_id=host["id"],
                    chat_id=555001,
                    telegram_user_id=555001,
                    paused=False,
                    open_internship_slugs=[],
                )
            )
            await session.commit()

    asyncio.run(_bind())

    sent = client.post(
        "/api/feedback",
        json={"kind": "idea", "body": "Хочу тёмную тему ещё темнее", "page": "/settings"},
        cookies=guest_c,
    )
    assert sent.status_code == 200, sent.text
    assert sent_tg
    assert sent_tg[0][0] == "bot-token"
    assert sent_tg[0][1] == 555001
    assert "пожелание" in sent_tg[0][2]
    assert "Настройки" in sent_tg[0][2]
    assert sent_mail
    assert sent_mail[0][0] == "HuntOS · пожелание · Настройки"
    del host_c


def test_feedback_ok_when_notify_fails(client: TestClient, monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    _guest, guest_c = _register(client, f"guest-{suffix}@hunt.test")

    async def boom(*_args, **_kwargs) -> None:
        raise RuntimeError("down")

    monkeypatch.setattr("app.api.feedback.notify_feedback", boom)
    sent = client.post(
        "/api/feedback",
        json={"kind": "bug", "body": "карточка не открывается совсем"},
        cookies=guest_c,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["ok"] is True
