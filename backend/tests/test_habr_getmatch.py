from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.clipper import detect_source
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.query_key import make_query_key
from app.services.scraper.sources.getmatch import normalize_getmatch_job, parse_initial_vacancy
from app.services.scraper.sources.habr import normalize_habr_job, parse_api_list, parse_search_rss

FIXTURES = Path(__file__).parent / "fixtures"


def test_query_key_habr_and_getmatch_casefold() -> None:
    a = make_query_key("habr", {"search": "Python", "remote": True, "s": ["2"]})
    b = make_query_key("habr", {"search": "python", "remote": True, "s": ["2"]})
    assert a == b
    c = make_query_key("getmatch", {"search": "QA", "specialty": "qa_auto", "location": "remote"})
    d = make_query_key("getmatch", {"search": "qa", "specialty": "qa_auto", "location": "remote"})
    assert c == d
    assert a != c
    hire = make_query_key("hirehi", {"search": "python"})
    assert a != hire


def test_habr_rss_and_jsonld_normalize() -> None:
    jobs = parse_search_rss((FIXTURES / "habr_search.rss").read_text())
    assert len(jobs) == 1
    item = jobs[0]
    assert item["id"] == "1000168375"
    assert item["title"] == "ML Разработчик"
    assert item["company"] == "True Engineering"
    assert "Python" in item["skills"] or "python" in [s.lower() for s in item["skills"]]

    html = (FIXTURES / "habr_vacancy.html").read_text()
    posted = extract_job_posting(html, page_url="https://career.habr.com/vacancies/1000168375")
    assert posted["salary_raw"] == "от 300000 до 400000 RUB"
    payload = normalize_habr_job({"id": "1000168375", **posted}, item)
    assert payload["source"] == "habr"
    assert payload["source_id"] == "1000168375"
    assert payload["title"] == "ML Разработчик"
    assert payload["company"] == "True Engineering"
    assert payload["work_format"] == "удалённо"
    assert payload["salary_min"] == 300000
    assert "RAG" in (payload["description"] or "") or "PyTorch" in (payload["description"] or "")


def test_getmatch_initial_vacancy_normalize() -> None:
    html = (FIXTURES / "getmatch_vacancy.html").read_text()
    detail = parse_initial_vacancy(html)
    assert detail["id"] == 6122
    payload = normalize_getmatch_job(detail)
    assert payload["source"] == "getmatch"
    assert payload["source_id"] == "6122"
    assert payload["title"] == "Backend (Python)"
    assert payload["company"] == "DevHub"
    assert payload["work_format"] == "удалённо"
    assert "Python" in payload["skills"]
    assert payload["salary_min"] == 200000


def test_getmatch_logotype_filename_normalizes_to_cdn() -> None:
    payload = normalize_getmatch_job(
        {
            "id": 33787,
            "position": "Go",
            "company": {"name": "2ГИС", "logotype": "549a17dc-3363-4bd7-a9e0-0b6a068a6f65.png"},
        }
    )
    assert payload["company_icon"] == (
        "https://getmatch.ru/uploads/companies_logos/549a17dc-3363-4bd7-a9e0-0b6a068a6f65.png"
    )


def test_habr_api_list_paginates() -> None:
    jobs, has_more = parse_api_list(
        {
            "list": [
                {
                    "id": 1000168375,
                    "href": "/vacancies/1000168375",
                    "title": "ML Разработчик",
                    "remoteWork": True,
                    "qualification": "Senior",
                    "company": {"title": "True Engineering", "logo": {"src": "https://logo.test/te.png"}},
                    "salary": {"formatted": "от 300000 до 400000 RUB"},
                    "skills": [{"title": "Python"}],
                    "locations": [{"title": "Новосибирск"}],
                }
            ],
            "meta": {"totalResults": 80, "perPage": 25, "currentPage": 1, "totalPages": 4},
        }
    )
    assert len(jobs) == 1
    assert jobs[0]["id"] == "1000168375"
    assert jobs[0]["company"] == "True Engineering"
    assert jobs[0]["work_format"] == "удалённо"
    assert "Python" in jobs[0]["skills"]
    assert has_more is True
    _, last = parse_api_list({"list": jobs, "meta": {"currentPage": 4, "totalPages": 4}})
    assert last is False


def test_clipper_detects_habr_and_getmatch() -> None:
    assert detect_source("https://career.habr.com/vacancies/1000168375") == ("habr", "1000168375")
    assert detect_source("https://getmatch.ru/vacancies/6122-backend-python") == ("getmatch", "6122")


def test_unknown_source_rejected(client: TestClient) -> None:
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"src-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    resp = client.post(
        "/api/scraper-configs",
        json={"name": "x", "source": "avito", "enabled": True, "query_params": {"search": "qa"}},
        cookies=cookies,
    )
    assert resp.status_code == 400
    assert "источник" in resp.text.lower()
