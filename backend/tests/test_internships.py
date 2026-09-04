from uuid import uuid4

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return dict(resp.cookies)


def test_internships_catalog_and_track(client: TestClient) -> None:
    cookies = _register(client, f"intern-{uuid4().hex[:8]}@hunt.test")
    listed = client.get("/api/internships?kind=internship", cookies=cookies)
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 25
    assert rows[0]["slug"]
    assert rows[0]["url"].startswith("http")

    yandex = next(row for row in rows if row["slug"] == "yandex-intern")
    assert yandex["catalog_status"] == "open"
    assert yandex["live_status"] in {None, "open", "waiting", "closed", "monitor"}
    assert yandex["track"]["status"] is None
    assert yandex.get("logo_url") and "yandex" in yandex["logo_url"].casefold()

    saved = client.put(
        "/api/internships/yandex-intern",
        json={"status": "applied", "notes": "осень 2026"},
        cookies=cookies,
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["track"]["status"] == "applied"
    assert body["track"]["notes"] == "осень 2026"

    schools = client.get("/api/internships?kind=school", cookies=cookies)
    assert schools.status_code == 200
    assert all(row["kind"] == "school" for row in schools.json())
    assert len(schools.json()) >= 10

    cleared = client.put("/api/internships/yandex-intern", json={"status": None, "notes": None}, cookies=cookies)
    assert cleared.status_code == 200
    assert cleared.json()["track"]["status"] is None
