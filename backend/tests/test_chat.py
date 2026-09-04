from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.chat import is_online, now_utc


def _session(resp) -> dict[str, str]:
    token = resp.cookies.get("hunt_session")
    assert token, resp.text
    return {"hunt_session": token}


def _register(client: TestClient, email: str) -> tuple[dict, dict[str, str]]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return resp.json(), _session(resp)


def _host_guest(client: TestClient, test_db_path: Path) -> tuple[dict, dict[str, str], dict, dict[str, str]]:
    suffix = uuid4().hex[:8]
    host, host_c = _register(client, f"host-{suffix}@hunt.test")
    if not host.get("is_host"):
        import sqlite3

        con = sqlite3.connect(test_db_path)
        con.execute("UPDATE users SET is_host = 0")
        con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (host["id"],))
        con.commit()
        con.close()
        host = client.get("/api/auth/me", cookies=host_c).json()
    guest, guest_c = _register(client, f"guest-{suffix}@hunt.test")
    return host, host_c, guest, guest_c


def test_is_online_window() -> None:
    stamp = now_utc()
    assert is_online(stamp, stamp) is True
    assert is_online(stamp - timedelta(seconds=89), stamp) is True
    assert is_online(stamp - timedelta(seconds=120), stamp) is False
    assert is_online(None, stamp) is False
    aware = datetime.now(UTC)
    assert is_online(aware, aware.replace(tzinfo=None)) is True


def test_guest_chats_only_with_admin(client: TestClient, test_db_path: Path) -> None:
    host, host_c, guest, guest_c = _host_guest(client, test_db_path)
    other, other_c = _register(client, f"other-{uuid4().hex[:8]}@hunt.test")

    inbox = client.get("/api/chat/inbox", cookies=guest_c)
    assert inbox.status_code == 200, inbox.text
    data = inbox.json()
    assert data["host"] is False
    assert data["admin"]["name"] == "Админ"
    assert len(data["threads"]) == 1
    thread_id = data["threads"][0]["id"]
    assert data["threads"][0]["peer_name"] == "Админ"
    assert data["threads"][0]["peer_id"] == host["id"]

    forbidden = client.post("/api/chat/open", json={"user_id": other["id"]}, cookies=guest_c)
    assert forbidden.status_code == 404

    sent = client.post(
        f"/api/chat/{thread_id}/messages",
        json={"body": "привет, это гость"},
        cookies=guest_c,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["mine"] is True
    assert sent.json()["body"] == "привет, это гость"

    host_inbox = client.get("/api/chat/inbox", cookies=host_c)
    assert host_inbox.status_code == 200, host_inbox.text
    host_data = host_inbox.json()
    assert host_data["host"] is True
    peer_ids = {row["peer_id"] for row in host_data["threads"]}
    assert guest["id"] in peer_ids
    assert other["id"] in peer_ids
    mine = next(row for row in host_data["threads"] if row["peer_id"] == guest["id"])
    assert mine["unread"] >= 1
    assert mine["peer_name"] == guest["email"]
    assert host_data["unread_total"] >= 1

    other_view = client.get(f"/api/chat/{thread_id}/messages", cookies=other_c)
    assert other_view.status_code == 404

    other_send = client.post(
        f"/api/chat/{thread_id}/messages",
        json={"body": "я не должен быть здесь"},
        cookies=other_c,
    )
    assert other_send.status_code == 404

    host_msgs = client.get(f"/api/chat/{thread_id}/messages", cookies=host_c)
    assert host_msgs.status_code == 200
    bodies = [row["body"] for row in host_msgs.json()]
    assert "привет, это гость" in bodies
    assert all(row["mine"] is False or row["sender_id"] == host["id"] for row in host_msgs.json())

    reply = client.post(
        f"/api/chat/{thread_id}/messages",
        json={"body": "принял, смотрю"},
        cookies=host_c,
    )
    assert reply.status_code == 200, reply.text

    guest_msgs = client.get(f"/api/chat/{thread_id}/messages", cookies=guest_c)
    assert "принял, смотрю" in {row["body"] for row in guest_msgs.json()}

    after_host = client.get("/api/chat/inbox", cookies=host_c).json()
    guest_row = next(row for row in after_host["threads"] if row["peer_id"] == guest["id"])
    assert guest_row["unread"] == 0


def test_chat_ignores_impersonation_header(client: TestClient, test_db_path: Path) -> None:
    host, host_c, guest, guest_c = _host_guest(client, test_db_path)
    thread_id = client.get("/api/chat/inbox", cookies=guest_c).json()["threads"][0]["id"]
    sent = client.post(
        f"/api/chat/{thread_id}/messages",
        json={"body": "пишу сам, не админ"},
        cookies=guest_c,
        headers={"X-Hunt-As": str(host["id"])},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["sender_id"] == guest["id"]
    assert sent.json()["mine"] is True

    host_sent = client.post(
        f"/api/chat/{thread_id}/messages",
        json={"body": "это хост"},
        cookies=host_c,
        headers={"X-Hunt-As": str(guest["id"])},
    )
    assert host_sent.status_code == 200, host_sent.text
    assert host_sent.json()["sender_id"] == host["id"]


def test_presence_flips_with_last_seen(client: TestClient, test_db_path: Path) -> None:
    host, host_c, guest, guest_c = _host_guest(client, test_db_path)
    guest_box = client.get("/api/chat/inbox", cookies=guest_c).json()
    assert "online" in guest_box["admin"]

    host_box = client.get("/api/chat/inbox", cookies=host_c).json()
    guest_row = next(row for row in host_box["threads"] if row["peer_id"] == guest["id"])
    assert guest_row["online"] is True
    assert guest_row["last_seen_at"]

    import sqlite3

    old = (datetime.now(UTC) - timedelta(hours=3)).replace(tzinfo=None).isoformat(sep=" ")
    con = sqlite3.connect(test_db_path)
    con.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (old, guest["id"]))
    con.commit()
    con.close()

    again = client.get("/api/chat/inbox", cookies=host_c).json()
    stale = next(row for row in again["threads"] if row["peer_id"] == guest["id"])
    assert stale["online"] is False
