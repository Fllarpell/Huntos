from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _session(client: TestClient) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    client.cookies.clear()
    resp = client.post(
        "/api/auth/register",
        json={"email": f"excl-{suffix}@hunt.test", "password": "password1"},
    )
    assert resp.status_code == 200, resp.text
    return {"hunt_session": client.cookies["hunt_session"]}


def _create(client: TestClient, cookies: dict[str, str], title: str, company: str) -> int:
    created = client.post("/api/vacancies", json={"title": title, "company": company}, cookies=cookies)
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_inbox_filter_drops_yandex_aliases(client: TestClient) -> None:
    cookies = _session(client)
    yandex = _create(client, cookies, "Backend", "Яндекс")
    taxi = _create(client, cookies, "Go", "Yandex Go")
    kuper = _create(client, cookies, "ML", "Купер")

    found = client.get("/api/vacancies", params=[("exclude_company", "яндекс")], cookies=cookies)
    assert found.status_code == 200, found.text
    ids = {row["id"] for row in found.json()["items"]}
    assert kuper in ids
    assert yandex not in ids
    assert taxi not in ids


def test_inbox_filter_drops_yandex_career_teams(client: TestClient) -> None:
    cookies = _session(client)
    clipped = client.post(
        "/api/vacancies/clip",
        json={
            "url": "https://yandex.ru/jobs/vacancies/backend-python-moscow",
            "title": "Backend",
            "company": "Маркет",
        },
        cookies=cookies,
    )
    assert clipped.status_code == 200, clipped.text
    yandex_team = clipped.json()["vacancy"]["id"]
    kuper = _create(client, cookies, "ML", "Купер")

    found = client.get("/api/vacancies", params=[("exclude_company", "яндекс")], cookies=cookies)
    assert found.status_code == 200, found.text
    ids = {row["id"] for row in found.json()["items"]}
    assert kuper in ids
    assert yandex_team not in ids


def test_thesis_exclude_companies_filters_hunt_inbox(client: TestClient) -> None:
    cookies = _session(client)
    yandex = _create(client, cookies, "Backend", "Yandex")
    kuper = _create(client, cookies, "ML", "Купер")
    created = client.post(
        "/api/theses",
        json={"name": "без яндекса", "exclude_companies": ["Яндекс"]},
        cookies=cookies,
    )
    assert created.status_code == 200, created.text
    hunt_id = created.json()["id"]
    assert created.json()["exclude_companies"] == ["Яндекс"]

    found = client.get("/api/vacancies", params={"hunt_id": hunt_id, "stage": "inbox"}, cookies=cookies)
    assert found.status_code == 200, found.text
    ids = {row["id"] for row in found.json()["items"]}
    assert kuper in ids
    assert yandex not in ids
