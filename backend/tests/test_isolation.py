from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


def _session(resp) -> dict[str, str]:
    token = resp.cookies.get("hunt_session")
    assert token, resp.text
    return {"hunt_session": token}


def _register(client: TestClient, email: str) -> tuple[dict, dict[str, str]]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return resp.json(), _session(resp)


def test_users_are_isolated_and_host_can_inspect(
    client: TestClient, test_db_path: Path
) -> None:
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
    assert host.get("is_host") is True
    guest, guest_c = _register(client, f"guest-{suffix}@hunt.test")
    assert "is_host" not in guest
    assert "can_observe" not in guest
    guest_me = client.get("/api/auth/me", cookies=guest_c).json()
    assert "is_host" not in guest_me
    assert "can_observe" not in guest_me

    created = client.post(
        "/api/vacancies",
        json={"title": "Go backend", "company": "Acme", "telegram_alias": "@hracme"},
        cookies=guest_c,
    )
    assert created.status_code == 200, created.text
    guest_vacancy_id = created.json()["id"]

    guest_list = client.get("/api/vacancies", cookies=guest_c)
    assert guest_list.status_code == 200
    assert guest_vacancy_id in {row["id"] for row in guest_list.json()["items"]}

    host_own = client.get("/api/vacancies", cookies=host_c)
    assert host_own.status_code == 200
    assert guest_vacancy_id not in {row["id"] for row in host_own.json()["items"]}

    as_guest = client.get(
        "/api/vacancies",
        cookies=host_c,
        headers={"X-Hunt-As": str(guest["id"])},
    )
    assert as_guest.status_code == 200
    assert guest_vacancy_id in {row["id"] for row in as_guest.json()["items"]}

    ignored_as = client.get(
        "/api/vacancies",
        cookies=guest_c,
        headers={"X-Hunt-As": str(host["id"])},
    )
    assert ignored_as.status_code == 200
    assert guest_vacancy_id in {row["id"] for row in ignored_as.json()["items"]}
    assert ignored_as.json()["items"][0]["id"] == guest_vacancy_id or guest_vacancy_id in {
        row["id"] for row in ignored_as.json()["items"]
    }

    guest_contacts = client.get("/api/contacts", cookies=guest_c)
    assert guest_contacts.status_code == 200
    assert any(row["telegram_alias"] == "hracme" for row in guest_contacts.json())

    host_contacts = client.get("/api/contacts", cookies=host_c)
    assert host_contacts.status_code == 200
    assert not any(row["telegram_alias"] == "hracme" for row in host_contacts.json())

    all_pool = client.get("/api/contacts", params={"pool": "all"}, cookies=host_c)
    assert all_pool.status_code == 200
    assert any(row["telegram_alias"] == "hracme" for row in all_pool.json())
    as_guest_contacts = client.get(
        "/api/contacts",
        cookies=host_c,
        headers={"X-Hunt-As": str(guest["id"])},
    )
    assert as_guest_contacts.status_code == 200
    assert any(row["telegram_alias"] == "hracme" for row in as_guest_contacts.json())

    assert client.get("/api/contacts", params={"pool": "all"}, cookies=guest_c).status_code == 403
    assert client.get("/api/telegram/pool", cookies=guest_c).status_code == 404
    joined = client.post("/api/telegram/join", cookies=guest_c)
    assert joined.status_code == 200, joined.text
    assert joined.json()["ok"] is True
    guest_google = client.get("/api/google/status", cookies=guest_c)
    assert guest_google.status_code == 200, guest_google.text
    assert guest_google.json()["connected"] is False
    assert client.get("/api/auth/users", cookies=guest_c).status_code == 404

    granted = client.patch(
        f"/api/auth/users/{guest['id']}",
        json={"can_observe": True},
        cookies=host_c,
    )
    assert granted.status_code == 200, granted.text
    assert granted.json().get("can_observe") is True
    observer = client.get("/api/auth/me", cookies=guest_c).json()
    assert observer.get("can_observe") is True
    assert "is_host" not in observer
    listed = client.get("/api/auth/users", cookies=guest_c)
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()} >= {host["id"], guest["id"]}

    as_host = client.get(
        "/api/vacancies",
        cookies=guest_c,
        headers={"X-Hunt-As": str(host["id"])},
    )
    assert as_host.status_code == 200
    assert guest_vacancy_id not in {row["id"] for row in as_host.json()["items"]}

    assert client.get("/api/contacts", params={"pool": "all"}, cookies=guest_c).status_code == 403
    assert client.patch(
        f"/api/auth/users/{host['id']}",
        json={"can_observe": True},
        cookies=guest_c,
    ).status_code == 404
