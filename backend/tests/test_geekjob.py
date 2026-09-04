from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.clipper import detect_source
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.query_key import make_query_key
from app.services.scraper.sources.geekjob import listing_has_more, normalize_geekjob_job, parse_search_html
from app.services.scraper.sources.geekjob_filters import geekjob_job_matches, listing_url_from_params, normalize_geekjob_params

FIXTURES = Path(__file__).parent / "fixtures"


def test_query_key_geekjob_casefold() -> None:
    a = make_query_key("geekjob", {"search": "Python", "stack": ["python"]})
    b = make_query_key("geekjob", {"search": "python", "stack": ["python"]})
    assert a == b
    habr = make_query_key("habr", {"search": "python"})
    assert a != habr


def test_geekjob_listing_skips_ads_and_jsonld_normalize() -> None:
    jobs = parse_search_html((FIXTURES / "geekjob_search.html").read_text())
    assert [item["id"] for item in jobs] == [
        "69e2482a2215b591570d4e22",
        "6a2c1624ebd40897150824df",
    ]
    assert jobs[0]["title"] == "Senior AI / ML Engineer"
    assert jobs[0]["company"] == "NEWHR"
    assert jobs[0]["company_icon"] and "storage/company" in jobs[0]["company_icon"]

    html = (FIXTURES / "geekjob_vacancy.html").read_text()
    posted = extract_job_posting(html, page_url="https://geekjob.ru/vacancy/69e2482a2215b591570d4e22")
    payload = normalize_geekjob_job({"id": "69e2482a2215b591570d4e22", **posted}, jobs[0])
    assert payload["source"] == "geekjob"
    assert payload["source_id"] == "69e2482a2215b591570d4e22"
    assert payload["title"] == "Senior AI / ML Engineer"
    assert payload["company"] == "Агентство NEWHR"
    assert payload["work_format"] == "удалённо"
    assert payload["salary_min"] == 400000
    assert "RAG" in (payload["description"] or "") or "PyTorch" in (payload["description"] or "")
    assert payload["company_icon"] and "geekjob.ru/storage/company" in payload["company_icon"]


def test_geekjob_listing_filters_common_search() -> None:
    jobs = parse_search_html((FIXTURES / "geekjob_search.html").read_text())
    ml = jobs[0]
    assert geekjob_job_matches(ml, {"search": "ml"})
    assert geekjob_job_matches(ml, {"stack": ["ml"]})
    assert not geekjob_job_matches(ml, {"search": "android"})


def test_clipper_detects_geekjob() -> None:
    assert detect_source("https://geekjob.ru/vacancy/69e2482a2215b591570d4e22") == (
        "geekjob",
        "69e2482a2215b591570d4e22",
    )


def test_geekjob_config_accepted(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"gj-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    resp = client.post(
        "/api/scraper-configs",
        json={"name": "", "source": "geekjob", "enabled": True, "query_params": {"search": "python"}},
        cookies=cookies,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "geekjob"
    assert body["query_params"]["search"] == "python"
    assert "geekjob.ru" in (body["listing_url"] or "")


def test_normalize_geekjob_params() -> None:
    assert normalize_geekjob_params({"search": " Python ", "stack": ["python"], "formats": ["remote"]}) == {
        "search": "Python",
        "stack": ["python"],
        "formats": ["remote"],
    }


def test_geekjob_listing_paginates() -> None:
    assert listing_url_from_params({"search": "python"}, page=1).endswith("qs=python")
    assert "page=2" in listing_url_from_params({"search": "python"}, page=2)
    html = '<a href="/?qs=python&page=2" rel="next">дальше</a>'
    assert listing_has_more(html, page=1, raw_count=2) is True
    assert listing_has_more("<ul></ul>", page=1, raw_count=2) is False
    assert listing_has_more("<ul></ul>", page=1, raw_count=20) is True
