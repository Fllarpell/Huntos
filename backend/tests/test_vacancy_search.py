from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_inbox_search_finds_cyrillic_company_casefold(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    client.cookies.clear()
    resp = client.post(
        "/api/auth/register",
        json={"email": f"kuper-{suffix}@hunt.test", "password": "password1"},
    )
    assert resp.status_code == 200, resp.text
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    created = client.post(
        "/api/vacancies",
        json={"title": "Python-разработчик", "company": "Купер"},
        cookies=cookies,
    )
    assert created.status_code == 200, created.text
    vacancy_id = created.json()["id"]

    found = client.get("/api/vacancies", params={"q": "купер"}, cookies=cookies)
    assert found.status_code == 200, found.text
    assert vacancy_id in {row["id"] for row in found.json()["items"]}

    found_title = client.get("/api/vacancies", params={"q": "КУПЕР"}, cookies=cookies)
    assert vacancy_id in {row["id"] for row in found_title.json()["items"]}


def test_inbox_hides_sales_and_support_titles(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    client.cookies.clear()
    resp = client.post(
        "/api/auth/register",
        json={"email": f"junk-{suffix}@hunt.test", "password": "password1"},
    )
    assert resp.status_code == 200, resp.text
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    sales = client.post(
        "/api/vacancies",
        json={"title": "Менеджер по продажам", "company": "Рога"},
        cookies=cookies,
    )
    keep = client.post(
        "/api/vacancies",
        json={"title": "Python-разработчик", "company": "Яндекс"},
        cookies=cookies,
    )
    assert sales.status_code == 200 and keep.status_code == 200
    listed = client.get("/api/vacancies", params={"stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in listed.json()["items"]}
    assert keep.json()["id"] in ids
    assert sales.json()["id"] not in ids
