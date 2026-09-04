from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.vacancy import PipelineStage
from app.services.salary_stats import corridor_from_vacancies, percentile, salary_corridor
from app.services.thesis import evaluate


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _thesis(**extra: object) -> SimpleNamespace:
    now = _now()
    data = {
        "created_at": now - timedelta(days=10),
        "days": 14,
        "min_sample": 8,
        "min_median_match": 55,
    }
    data.update(extra)
    return SimpleNamespace(**data)


def _vac(**extra: object) -> SimpleNamespace:
    now = _now()
    data = {
        "match_score": 70,
        "company": "Kuper",
        "published_at": now - timedelta(days=40),
        "created_at": now,
        "pipeline_stage": PipelineStage.INBOX,
        "outreach_at": None,
        "telegram_alias": None,
        "contact_email": None,
        "contact_phone": None,
        "salary_min": None,
        "salary_currency": "RUB",
        "source": "habr",
        "grade": "middle",
        "title": "Backend engineer",
        "skills": ["python"],
        "category": "development",
    }
    data.update(extra)
    return SimpleNamespace(**data)


def test_percentile_and_corridor() -> None:
    assert percentile([100, 200, 300, 400], 25) == 175
    assert percentile([100, 200, 300, 400], 50) == 250
    assert percentile([100, 200, 300, 400], 75) == 325
    empty = salary_corridor([])
    assert empty["n"] == 0
    assert empty["median"] is None
    stats = salary_corridor([200_000, 250_000, 300_000, 350_000], open_n=3)
    assert stats["n"] == 4
    assert stats["p25"] is not None
    assert stats["median"] is not None
    assert stats["p75"] is not None
    assert stats["open_share"] == 0.75


def test_corridor_from_vacancies_skips_non_rub() -> None:
    rows = [
        _vac(salary_min=200_000, source="habr"),
        _vac(salary_min=220_000, source="getmatch"),
        _vac(salary_min=90_000, salary_currency="USD", source="hh"),
        _vac(salary_min=None, source="hh"),
    ]
    corridor = corridor_from_vacancies(rows)
    assert corridor["n"] == 2
    assert corridor["open_share"] == 1.0
    assert corridor["by_source"] == {"habr": 1, "getmatch": 1}


def test_corridor_splits_by_grade_and_specialty() -> None:
    rows = [
        _vac(salary_min=150_000, grade="junior", title="Junior Python developer", skills=["python"], source="habr"),
        _vac(salary_min=160_000, grade="junior", title="Junior Python", skills=["python"], source="habr"),
        _vac(salary_min=170_000, grade="junior", title="Python junior", skills=["python"], source="getmatch"),
        _vac(salary_min=300_000, grade="senior", title="Senior Go engineer", skills=["go"], source="habr"),
        _vac(salary_min=320_000, grade="senior", title="Go senior", skills=["go"], source="getmatch"),
        _vac(salary_min=340_000, grade="senior", title="Senior Golang", skills=["go"], source="hh"),
    ]
    corridor = corridor_from_vacancies(rows)
    assert corridor["n"] == 6
    grades = {item["key"]: item for item in corridor["by_grade"]}
    assert grades["junior"]["n"] == 3
    assert grades["senior"]["n"] == 3
    assert grades["junior"]["median"] < grades["senior"]["median"]
    specialties = {item["key"]: item for item in corridor["by_specialty"]}
    assert specialties["python"]["n"] == 3
    assert specialties["go"]["n"] == 3


def test_corridor_filter_grade_and_specialty_intersection() -> None:
    rows = [
        _vac(salary_min=150_000, grade="junior", title="Junior Python", skills=["python"], source="habr"),
        _vac(salary_min=160_000, grade="junior", title="Junior Python", skills=["python"], source="hh"),
        _vac(salary_min=170_000, grade="junior", title="Junior Python", skills=["python"], source="career"),
        _vac(salary_min=300_000, grade="senior", title="Senior Python", skills=["python"], source="habr"),
        _vac(salary_min=320_000, grade="junior", title="Junior Go", skills=["go"], source="habr"),
    ]
    sliced = corridor_from_vacancies(rows, grade="junior", specialty="python")
    assert sliced["n"] == 3
    assert sliced["grade"] == "junior"
    assert sliced["specialty"] == "python"
    assert sliced["median"] == 160_000


def test_evaluate_includes_salary_corridor() -> None:
    rows = [
        _vac(
            salary_min=180_000 + i * 20_000,
            source="habr" if i % 2 == 0 else "hh",
            grade="middle" if i < 3 else "senior",
            title="Python backend",
            skills=["python"],
        )
        for i in range(6)
    ]
    stats = evaluate(_thesis(), rows)  # type: ignore[arg-type]
    corridor = stats["salary_corridor"]
    assert corridor["n"] == 6
    assert corridor["p25"] is not None
    assert corridor["median"] is not None
    assert corridor["p75"] is not None
    assert corridor["p25"] <= corridor["median"] <= corridor["p75"]
    assert corridor["by_source"]["habr"] == 3
    assert corridor["by_source"]["hh"] == 3
    assert len(corridor["by_grade"]) >= 2
    assert any(item["key"] == "python" for item in corridor["by_specialty"])


def test_evaluate_counts_inbox_even_when_published_long_ago() -> None:
    rows = [_vac() for _ in range(8)]
    stats = evaluate(_thesis(), rows)  # type: ignore[arg-type]
    assert stats["inbox"] == 8
    assert stats["sample"] == 8
    assert stats["fresh_24h"] == 8
    assert stats["verdict"] == "alive"
    assert "inbox" in stats["reason"]


def test_evaluate_outreach_without_replies_stays_weak_if_inbox_is_alive() -> None:
    inbox = [_vac() for _ in range(6)]
    funnel = [
        _vac(pipeline_stage=PipelineStage.WAITING, outreach_at=_now(), created_at=_now() - timedelta(days=2))
        for _ in range(5)
    ]
    stats = evaluate(_thesis(), inbox + funnel)  # type: ignore[arg-type]
    assert stats["outreach"] == 5
    assert stats["replies"] == 0
    assert stats["inbox"] == 6
    assert stats["verdict"] == "weak"
    assert "inbox" in stats["reason"]


def test_evaluate_outreach_without_inbox_is_dead() -> None:
    funnel = [
        _vac(pipeline_stage=PipelineStage.WAITING, outreach_at=_now(), created_at=_now() - timedelta(days=2))
        for _ in range(8)
    ]
    stats = evaluate(_thesis(created_at=_now() - timedelta(days=20)), funnel)  # type: ignore[arg-type]
    assert stats["inbox"] == 0
    assert stats["outreach"] >= 5
    assert stats["verdict"] == "dead"


def test_thesis_api_sample_includes_inbox(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"thesis-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    for index in range(8):
        created = client.post("/api/vacancies", json={"title": f"Python backend {index}"}, cookies=cookies)
        assert created.status_code == 200, created.text
    listed = client.get("/api/theses", cookies=cookies)
    assert listed.status_code == 200
    assert listed.json() == []

    saved = client.post(
        "/api/theses",
        json={"name": "python", "role_query": "Python", "min_sample": 8, "days": 14},
        cookies=cookies,
    )
    assert saved.status_code == 200, saved.text
    stats = saved.json()["stats"]
    assert stats["sample"] >= 8
    assert stats["inbox"] >= 8
    assert stats["verdict"] == "alive"
    assert saved.json()["last_verdict"] == "alive"

    extra = client.post("/api/vacancies", json={"title": "Python senior 9"}, cookies=cookies)
    assert extra.status_code == 200
    again = client.get("/api/theses", cookies=cookies)
    assert again.status_code == 200
    assert again.json()[0]["stats"]["inbox"] >= 9
    assert again.json()[0]["stats"]["sample"] >= 9
