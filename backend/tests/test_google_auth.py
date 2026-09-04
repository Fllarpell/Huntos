from __future__ import annotations

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


async def _save_oauth(profile, payload: dict) -> None:
    from app.services.crypto import seal

    profile.google_refresh_token = seal(payload["refresh_token"])
    profile.google_access_token = seal(payload["access_token"])
    profile.google_email = "google@example.com"


def test_google_login_unavailable_without_keys(client: TestClient, monkeypatch) -> None:
    async def _empty(session, profile=None):  # noqa: ANN001
        return "", ""

    monkeypatch.setattr("app.api.auth.resolved_client_credentials", _empty)
    client.cookies.clear()
    status = client.get("/api/auth/google")
    assert status.status_code == 200
    assert status.json()["available"] is False
    start = client.post("/api/auth/google")
    assert start.status_code == 400


def test_google_login_creates_account(client: TestClient, test_db_path, monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    host, host_c = _register(client, f"host-{suffix}@hunt.test")
    if not host.get("is_host"):
        import sqlite3

        con = sqlite3.connect(test_db_path)
        con.execute("UPDATE users SET is_host = 0")
        con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (host["id"],))
        con.commit()
        con.close()
    saved = client.put(
        "/api/google/client",
        json={"google_client_id": "cid.apps.googleusercontent.com", "google_client_secret": "secret"},
        cookies=host_c,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["client_configured"] is True

    available = client.get("/api/auth/google")
    assert available.json()["available"] is True

    client.cookies.clear()
    start = client.post("/api/auth/google")
    assert start.status_code == 200, start.text
    url = start.json()["url"]
    assert "accounts.google.com" in url
    assert "openid" in url
    assert "localhost" in url
    state = start.cookies.get("hunt_google_oauth")
    assert state and state.startswith("login:")
    assert start.cookies.get("hunt_google_callback")

    async def _exchange(code: str, client_id: str, client_secret: str, callback: str | None = None) -> dict:
        assert code == "ok-code"
        assert client_id
        return {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}

    async def _info(access_token: str) -> dict:
        assert access_token == "at"
        return {"id": f"sub-{suffix}", "email": f"google-{suffix}@gmail.com", "verified_email": True}

    async def _calendar(profile) -> str:
        profile.google_calendar_id = "hunt-cal"
        return "hunt-cal"

    monkeypatch.setattr("app.api.google.exchange_code", _exchange)
    monkeypatch.setattr("app.api.google.fetch_userinfo", _info)
    monkeypatch.setattr("app.api.google.save_oauth", _save_oauth)
    monkeypatch.setattr("app.api.google.ensure_hunt_calendar", _calendar)

    bounce = client.get(
        "/api/google/callback",
        params={"code": "ok-code", "state": state},
        cookies={"hunt_google_oauth": state},
        follow_redirects=False,
    )
    assert bounce.status_code == 302, bounce.text
    location = bounce.headers["location"]
    assert location.endswith("/?new=1") or location.endswith("/")
    session = bounce.cookies.get("hunt_session")
    assert session
    me = client.get("/api/auth/me", cookies={"hunt_session": session}).json()
    assert me["email"] == f"google-{suffix}@gmail.com"
    assert "is_host" not in me
    assert "can_observe" not in me


def test_callback_uri_follows_allowed_origin(monkeypatch) -> None:
    from app.services.google_calendar import callback_uri_from_headers

    monkeypatch.setattr("app.services.google_calendar.settings.allow_origins", "https://127.0.0.1:8443")
    assert (
        callback_uri_from_headers({"origin": "https://127.0.0.1:8443"})
        == "https://127.0.0.1:8443/api/google/callback"
    )
    assert "localhost:3000" in callback_uri_from_headers({"origin": "https://evil.example"})


def test_google_login_url_uses_request_origin(client: TestClient, test_db_path, monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    host, host_c = _register(client, f"host-{suffix}@hunt.test")
    if not host.get("is_host"):
        import sqlite3

        con = sqlite3.connect(test_db_path)
        con.execute("UPDATE users SET is_host = 0")
        con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (host["id"],))
        con.commit()
        con.close()
    saved = client.put(
        "/api/google/client",
        json={"google_client_id": "cid.apps.googleusercontent.com", "google_client_secret": "secret"},
        cookies=host_c,
    )
    assert saved.status_code == 200, saved.text
    monkeypatch.setattr(
        "app.services.google_calendar.settings.allow_origins",
        "https://127.0.0.1:8443",
    )
    client.cookies.clear()
    start = client.post("/api/auth/google", headers={"Origin": "https://127.0.0.1:8443"})
    assert start.status_code == 200, start.text
    from urllib.parse import parse_qs, unquote, urlparse

    query = parse_qs(urlparse(start.json()["url"]).query)
    assert unquote(query["redirect_uri"][0]) == "https://127.0.0.1:8443/api/google/callback"
    assert start.cookies.get("hunt_google_callback", "").strip('"') == "https://127.0.0.1:8443/api/google/callback"


def test_google_login_does_not_attach_to_password_account(client: TestClient, test_db_path, monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    email = f"victim-{suffix}@hunt.test"
    host, host_c = _register(client, f"host-{suffix}@hunt.test")
    if not host.get("is_host"):
        import sqlite3

        con = sqlite3.connect(test_db_path)
        con.execute("UPDATE users SET is_host = 0")
        con.execute("UPDATE users SET is_host = 1 WHERE id = ?", (host["id"],))
        con.commit()
        con.close()
    saved = client.put(
        "/api/google/client",
        json={"google_client_id": "cid.apps.googleusercontent.com", "google_client_secret": "secret"},
        cookies=host_c,
    )
    assert saved.status_code == 200, saved.text
    victim, victim_c = _register(client, email)

    async def _exchange(code: str, client_id: str, client_secret: str, callback: str | None = None) -> dict:
        return {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}

    async def _info(access_token: str) -> dict:
        return {"id": f"sub-{suffix}", "email": email, "verified_email": True}

    monkeypatch.setattr("app.api.google.exchange_code", _exchange)
    monkeypatch.setattr("app.api.google.fetch_userinfo", _info)

    client.cookies.clear()
    start = client.post("/api/auth/google")
    state = start.cookies.get("hunt_google_oauth")
    bounce = client.get(
        "/api/google/callback",
        params={"code": "ok-code", "state": state},
        cookies={"hunt_google_oauth": state},
        follow_redirects=False,
    )
    assert bounce.status_code == 302
    assert "email-taken" in bounce.headers["location"]
    assert not bounce.cookies.get("hunt_session")
    me = client.get("/api/auth/me", cookies=victim_c)
    assert me.status_code == 200
    assert me.json()["id"] == victim["id"]
