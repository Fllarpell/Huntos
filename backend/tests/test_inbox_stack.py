from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models.scraper_config import ScraperConfig
from app.models.user import User
from app.models.vacancy import ScoringStatus, Vacancy
from app.services.fingerprint import fingerprints_close, vacancy_fingerprint
from app.services.scraper.engine import restore_overmerged_duplicates, upsert_vacancy


def _register(client: TestClient, email: str) -> dict[str, str]:
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={"email": email, "password": "password1"})
    assert resp.status_code == 200, resp.text
    return {"hunt_session": resp.cookies["hunt_session"]}


def _user_id() -> int:
    async def inner() -> int:
        async with SessionLocal() as session:
            row = (await session.execute(select(User).order_by(User.id.desc()))).scalars().first()
            assert row is not None
            return int(row.id)

    return asyncio.run(inner())


def test_inbox_q_go_keeps_go_drops_frontend(client: TestClient) -> None:
    cookies = _register(client, f"stack-q-{uuid4().hex[:8]}@hunt.test")
    go = client.post("/api/vacancies", json={"title": "Go-разработчик", "company": "Авито"}, cookies=cookies)
    fe = client.post("/api/vacancies", json={"title": "Frontend Engineer", "company": "VK"}, cookies=cookies)
    assert go.status_code == 200 and fe.status_code == 200
    go_id, fe_id = go.json()["id"], fe.json()["id"]
    assert "go" in (go.json().get("stack_ids") or [])

    found = client.get("/api/vacancies", params={"q": "go", "stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in found.json()["items"]}
    assert go_id in ids
    assert fe_id not in ids

    found_fe = client.get("/api/vacancies", params={"stack": "frontend", "stage": "inbox"}, cookies=cookies)
    ids_fe = {row["id"] for row in found_fe.json()["items"]}
    assert fe_id in ids_fe
    assert go_id not in ids_fe


def test_inbox_q_java_skips_javascript(client: TestClient) -> None:
    cookies = _register(client, f"java-q-{uuid4().hex[:8]}@hunt.test")
    java = client.post(
        "/api/vacancies",
        json={"title": "Java-разработчик", "company": "Сбер", "skills": ["Java", "Spring"]},
        cookies=cookies,
    )
    js = client.post(
        "/api/vacancies",
        json={"title": "Frontend Engineer (JavaScript)", "company": "VK", "skills": ["JavaScript", "React"]},
        cookies=cookies,
    )
    assert java.status_code == 200 and js.status_code == 200
    java_id, js_id = java.json()["id"], js.json()["id"]

    found = client.get("/api/vacancies", params={"q": "java", "stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in found.json()["items"]}
    assert java_id in ids
    assert js_id not in ids


def test_inbox_q_devops_via_kubernetes_alias(client: TestClient) -> None:
    cookies = _register(client, f"k8s-q-{uuid4().hex[:8]}@hunt.test")
    devops = client.post(
        "/api/vacancies",
        json={"title": "DevOps / Kubernetes", "company": "Авито", "skills": ["Kubernetes", "Terraform"]},
        cookies=cookies,
    )
    java = client.post(
        "/api/vacancies",
        json={"title": "Java-разработчик", "company": "Сбер", "skills": ["Java"]},
        cookies=cookies,
    )
    assert devops.status_code == 200 and java.status_code == 200
    devops_id, java_id = devops.json()["id"], java.json()["id"]

    found = client.get("/api/vacancies", params={"q": "kubernetes", "stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in found.json()["items"]}
    assert devops_id in ids
    assert java_id not in ids


def test_inbox_q_java_ignores_ml_laundry_list_skills(client: TestClient) -> None:
    cookies = _register(client, f"java-ml-{uuid4().hex[:8]}@hunt.test")
    ml = client.post(
        "/api/vacancies",
        json={
            "title": "ML Engineer for production AI systems",
            "company": "X",
            "skills": ["python", "pytorch", "rag", "langchain", "java", "go"],
        },
        cookies=cookies,
    )
    java = client.post(
        "/api/vacancies",
        json={"title": "Старший бэкенд-разработчик", "company": "Y", "skills": ["Java"]},
        cookies=cookies,
    )
    assert ml.status_code == 200 and java.status_code == 200
    ml_id, java_id = ml.json()["id"], java.json()["id"]
    found = client.get("/api/vacancies", params={"q": "java", "stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in found.json()["items"]}
    assert java_id in ids
    assert ml_id not in ids


def test_inbox_q_nlp_skips_java_even_with_polluted_stack(client: TestClient) -> None:
    cookies = _register(client, f"nlp-q-{uuid4().hex[:8]}@hunt.test")
    nlp = client.post(
        "/api/vacancies",
        json={"title": "ML-инженер (NLP / LLM)", "company": "Яндекс", "skills": ["Python", "NLP"]},
        cookies=cookies,
    )
    java = client.post(
        "/api/vacancies",
        json={"title": "Java-разработчик", "company": "Сбер", "skills": ["Java", "Spring"]},
        cookies=cookies,
    )
    assert nlp.status_code == 200 and java.status_code == 200
    nlp_id, java_id = nlp.json()["id"], java.json()["id"]

    async def pollute() -> None:
        async with SessionLocal() as session:
            row = await session.get(Vacancy, java_id)
            assert row is not None
            row.stack_ids = ["java", "ml", "python", "go", "frontend"]
            await session.commit()

    asyncio.run(pollute())

    found = client.get("/api/vacancies", params={"q": "nlp", "stage": "inbox"}, cookies=cookies)
    assert found.status_code == 200
    ids = {row["id"] for row in found.json()["items"]}
    assert nlp_id in ids
    assert java_id not in ids


def test_search_provenance_and_filter(client: TestClient) -> None:
    cookies = _register(client, f"prov-{uuid4().hex[:8]}@hunt.test")
    user_id = _user_id()

    async def inner() -> tuple[int, int]:
        async with SessionLocal() as session:
            go = ScraperConfig(user_id=user_id, name="Go · HH", source="hh", query_params={"stack": ["go"]}, enabled=True)
            fe = ScraperConfig(
                user_id=user_id, name="Frontend · Яндекс", source="career", query_params={"stack": ["frontend"], "company": "yandex"}, enabled=True
            )
            session.add_all([go, fe])
            await session.flush()
            payload = {
                "source": "hh",
                "source_id": f"hh-{uuid4().hex[:8]}",
                "title": "Go-разработчик",
                "company": "Яндекс",
                "source_url": "https://hh.ru/vacancy/1",
            }
            vacancy, _kind = await upsert_vacancy(session, payload, scraper_config_id=go.id, user_id=user_id)
            same, _again = await upsert_vacancy(session, payload, scraper_config_id=fe.id, user_id=user_id)
            await session.commit()
            assert vacancy.id == same.id
            return vacancy.id, go.id

    vacancy_id, go_search = asyncio.run(inner())
    listed = client.get("/api/vacancies", params={"search_id": go_search, "stage": "inbox"}, cookies=cookies)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert vacancy_id in {row["id"] for row in items}
    card = next(row for row in items if row["id"] == vacancy_id)
    names = {item["name"] for item in card.get("searches") or []}
    assert "Go · HH" in names
    assert "Frontend · Яндекс" in names


def test_hh_and_yandex_career_marked_duplicate(client: TestClient) -> None:
    cookies = _register(client, f"dup-{uuid4().hex[:8]}@hunt.test")
    user_id = _user_id()

    async def inner() -> int:
        async with SessionLocal() as session:
            career, _ = await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "yandex:15322",
                    "title": "Backend-разработчик Python",
                    "company": "Яндекс",
                    "source_url": "https://yandex.ru/jobs/vacancies/backend-python-moscow",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            hh, kind = await upsert_vacancy(
                session,
                {
                    "source": "hh",
                    "source_id": "12345678",
                    "title": "Python-разработчик backend (Москва)",
                    "company": "Yandex",
                    "source_url": "https://hh.ru/vacancy/12345678",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            await session.commit()
            assert kind == "merged"
            assert hh.id == career.id
            return career.id

    vacancy_id = asyncio.run(inner())
    listed = client.get("/api/vacancies", params={"stage": "inbox"}, cookies=cookies)
    items = listed.json()["items"]
    assert {row["id"] for row in items} == {vacancy_id}
    card = items[0]
    extras = card.get("extra_sources") or []
    assert any(item.get("source") == "hh" for item in extras)
    assert any("hh.ru" in str(item.get("label") or item.get("source_url") or "") for item in extras)


def test_compact_extra_sources_one_label_per_board() -> None:
    from app.services.extra_sources import compact_extra_sources

    extras = compact_extra_sources(
        [
            {"source": "career", "source_id": "vk:1", "label": "VK"},
            {"source": "career", "source_id": "vk:2", "label": "VK"},
            {"source": "career", "source_id": "vk:3", "label": "VK"},
            {"source": "hirehi", "source_id": "a", "label": "HireHi"},
            {"source": "hirehi", "source_id": "b", "label": "HireHi"},
        ],
        source="getmatch",
        source_id="gm-1",
    )
    assert [item["label"] for item in extras] == ["VK", "HireHi"]


def test_same_career_board_listings_stay_separate(client: TestClient) -> None:
    cookies = _register(client, f"vk-sep-{uuid4().hex[:8]}@hunt.test")
    user_id = _user_id()

    async def inner() -> tuple[int, int]:
        async with SessionLocal() as session:
            first, kind_a = await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "vk:111",
                    "title": "Старший продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://team.vk.company/vacancy/111",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            second, kind_b = await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "vk:222",
                    "title": "Продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://team.vk.company/vacancy/222",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            await session.commit()
            assert kind_a == "new"
            assert kind_b == "new"
            return first.id, second.id

    left, right = asyncio.run(inner())
    assert left != right
    listed = client.get("/api/vacancies", params={"stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in listed.json()["items"]}
    assert left in ids and right in ids
    card = next(row for row in listed.json()["items"] if row["id"] == left)
    assert not (card.get("extra_sources") or [])


def test_cross_source_keeps_single_board_extra(client: TestClient) -> None:
    cookies = _register(client, f"dup-once-{uuid4().hex[:8]}@hunt.test")
    user_id = _user_id()

    async def inner() -> int:
        async with SessionLocal() as session:
            gm, _ = await upsert_vacancy(
                session,
                {
                    "source": "getmatch",
                    "source_id": "gm-analyst",
                    "title": "Старший продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://getmatch.ru/vacancies/gm-analyst",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "vk:111",
                    "title": "Старший продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://team.vk.company/vacancy/111",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "vk:222",
                    "title": "Продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://team.vk.company/vacancy/222",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            await session.commit()
            return gm.id

    vacancy_id = asyncio.run(inner())
    listed = client.get("/api/vacancies", params={"stage": "inbox"}, cookies=cookies)
    items = listed.json()["items"]
    card = next(row for row in items if row["id"] == vacancy_id)
    extras = card.get("extra_sources") or []
    labels = [item.get("label") for item in extras]
    assert labels.count("VK") <= 1
    assert "VK + VK" not in " + ".join(str(x) for x in labels)
    assert len(items) >= 2


def test_restore_same_source_stubs(client: TestClient) -> None:
    cookies = _register(client, f"restore-{uuid4().hex[:8]}@hunt.test")
    user_id = _user_id()

    async def inner() -> tuple[int, int, int]:
        async with SessionLocal() as session:
            first, _ = await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "vk:restore-1",
                    "title": "Продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://team.vk.company/vacancy/restore-1",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            second, _ = await upsert_vacancy(
                session,
                {
                    "source": "career",
                    "source_id": "vk:restore-2",
                    "title": "Старший продуктовый аналитик",
                    "company": "VK",
                    "source_url": "https://team.vk.company/vacancy/restore-2",
                },
                scraper_config_id=None,
                user_id=user_id,
            )
            row = await session.get(Vacancy, second.id)
            assert row is not None
            row.duplicate_of_id = first.id
            row.scoring_status = ScoringStatus.SKIPPED
            await session.commit()
            n = await restore_overmerged_duplicates(session)
            return first.id, second.id, n

    left, right, restored = asyncio.run(inner())
    assert restored >= 1
    listed = client.get("/api/vacancies", params={"stage": "inbox"}, cookies=cookies)
    ids = {row["id"] for row in listed.json()["items"]}
    assert left in ids and right in ids



def test_yandex_fingerprint_ignores_city_and_alias() -> None:
    a = vacancy_fingerprint("Senior Python-разработчик (Москва)", "Яндекс")
    b = vacancy_fingerprint("Python разработчик backend", "Yandex")
    assert a.split("|", 1)[0] == b.split("|", 1)[0] == "yandex"
    assert fingerprints_close(a, b)


def test_go_and_python_same_company_are_not_duplicates() -> None:
    go = vacancy_fingerprint("Go-разработчик backend", "Яндекс")
    py = vacancy_fingerprint("Python-разработчик backend", "Yandex")
    assert not fingerprints_close(go, py)


def test_frontend_title_aliases_are_duplicates() -> None:
    hh = vacancy_fingerprint("Frontend-разработчик", "Яндекс")
    career = vacancy_fingerprint("Frontend Engineer", "Yandex")
    assert fingerprints_close(hh, career)
