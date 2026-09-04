from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _session(client: TestClient) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    client.cookies.clear()
    resp = client.post(
        "/api/auth/register",
        json={"email": f"steps-{suffix}@hunt.test", "password": "password1"},
    )
    assert resp.status_code == 200, resp.text
    return {"hunt_session": client.cookies["hunt_session"]}


def _vacancy(client: TestClient, cookies: dict[str, str]) -> int:
    created = client.post("/api/vacancies", json={"title": "Go", "company": "VK"}, cookies=cookies)
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_interview_step_leaves_inbox_to_tech_interview(client: TestClient) -> None:
    cookies = _session(client)
    vacancy_id = _vacancy(client, cookies)
    assert client.get(f"/api/vacancies/{vacancy_id}", cookies=cookies).json()["pipeline_stage"] == "inbox"

    saved = client.post(
        f"/api/vacancies/{vacancy_id}/events",
        json={"kind": "interview", "starts_at": "2026-09-10T15:00:00"},
        cookies=cookies,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["pipeline_stage"] == "interview"
    assert body["events"][0]["kind"] == "interview"


def test_screening_step_moves_to_screening_column(client: TestClient) -> None:
    cookies = _session(client)
    vacancy_id = _vacancy(client, cookies)
    saved = client.post(
        f"/api/vacancies/{vacancy_id}/events",
        json={"kind": "screening", "starts_at": "2026-09-10T15:00:00"},
        cookies=cookies,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["pipeline_stage"] == "screening"


def test_assignment_step_keeps_inbox_and_stores_deadline(client: TestClient) -> None:
    cookies = _session(client)
    vacancy_id = _vacancy(client, cookies)
    saved = client.post(
        f"/api/vacancies/{vacancy_id}/events",
        json={"kind": "assignment", "starts_at": "2026-09-12T18:00:00"},
        cookies=cookies,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["pipeline_stage"] == "inbox"
    assert body["events"][0]["kind"] == "assignment"
    assert body["events"][0]["starts_at"].startswith("2026-09-12T18:00")


def test_step_does_not_demote_from_interview(client: TestClient) -> None:
    cookies = _session(client)
    vacancy_id = _vacancy(client, cookies)
    client.post(
        f"/api/vacancies/{vacancy_id}/events",
        json={"kind": "interview", "starts_at": "2026-09-10T15:00:00"},
        cookies=cookies,
    )
    saved = client.post(
        f"/api/vacancies/{vacancy_id}/events",
        json={"kind": "screening", "starts_at": "2026-09-11T12:00:00"},
        cookies=cookies,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["pipeline_stage"] == "interview"
