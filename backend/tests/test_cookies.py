from fastapi import Response
from fastapi.testclient import TestClient

from app.config import Settings
from app.services.auth import cookie_kwargs, set_session_cookie


def test_cookie_secure_follows_env() -> None:
    assert Settings.model_construct(app_env="dev").cookie_secure() is False
    assert Settings.model_construct(app_env="test").cookie_secure() is False
    assert Settings.model_construct(app_env="prod").cookie_secure() is True


def test_register_sets_httponly_session(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "wave-a@example.com", "password": "not-a-real-password"},
    )
    assert response.status_code == 200
    cookie = response.headers.get("set-cookie", "").lower()
    assert "hunt_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    # APP_ENV=test → Secure off so TestClient over http can store the cookie
    assert "secure" not in cookie


def test_prod_cookie_kwargs_set_secure() -> None:
    from app.config import settings

    previous = settings.app_env
    settings.app_env = "prod"
    try:
        kwargs = cookie_kwargs(max_age=60)
        assert kwargs["secure"] is True
        assert kwargs["httponly"] is True
        response = Response()
        set_session_cookie(response, "token")
        header = response.headers.get("set-cookie", "").lower()
        assert "secure" in header
        assert "httponly" in header
    finally:
        settings.app_env = previous


def test_cors_origin_list_splits_csv() -> None:
    parsed = Settings.model_construct(
        allow_origins="https://jobs.example.com, http://localhost:3000"
    )
    assert parsed.cors_origin_list() == [
        "https://jobs.example.com",
        "http://localhost:3000",
    ]
