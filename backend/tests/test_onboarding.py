from uuid import uuid4

from app.services.onboarding import hunt_name_from_resume
from app.services.telegram_bot import urls_in_text


def test_urls_in_text_strips_punctuation() -> None:
    text = "смотри https://hh.ru/vacancy/12345) и ещё https://hirehi.ru/dev/foo-1"
    assert urls_in_text(text) == ["https://hh.ru/vacancy/12345", "https://hirehi.ru/dev/foo-1"]


def test_urls_in_text_empty() -> None:
    assert urls_in_text("привет") == []
    assert urls_in_text("") == []


def test_hunt_name_from_resume_uses_stack() -> None:
    assert hunt_name_from_resume("python backend moscow", ["python", "docker"]) == "Python"


def test_onboarding_needed_for_empty_account(client) -> None:
    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"onb-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    row = client.get("/api/onboarding/status", cookies=cookies)
    assert row.status_code == 200, row.text
    data = row.json()
    assert data["needed"] is True
    assert data["has_resume"] is False
    assert data["inbox_count"] == 0


def test_onboarding_seed_after_resume(client) -> None:
    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"onb2-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    saved = client.put(
        "/api/settings/profile",
        json={"resume_text": "Python backend engineer. FastAPI, PostgreSQL, Docker."},
        cookies=cookies,
    )
    assert saved.status_code == 200, saved.text
    seeded = client.post("/api/onboarding/seed", cookies=cookies)
    assert seeded.status_code == 200, seeded.text
    data = seeded.json()
    assert data["has_resume"] is True
    assert data["needed"] is False
    assert data["hunt_id"] is not None
    status = client.get("/api/onboarding/status", cookies=cookies)
    assert status.json()["has_resume"] is True
    assert status.json()["needed"] is False


def test_urls_in_text_strips_punctuation() -> None:
    text = "смотри https://hh.ru/vacancy/12345) и ещё https://hirehi.ru/dev/foo-1"
    assert urls_in_text(text) == ["https://hh.ru/vacancy/12345", "https://hirehi.ru/dev/foo-1"]


def test_urls_in_text_empty() -> None:
    assert urls_in_text("привет") == []
    assert urls_in_text("") == []


def test_hunt_name_from_resume_uses_stack() -> None:
    assert hunt_name_from_resume("python backend moscow", ["python", "docker"]) == "Python"
