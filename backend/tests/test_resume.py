import asyncio
import json

from app.services.auth import SESSION_HEADER
from app.services.resume import (
    fill_resume_from_text,
    flatten_resume,
    hydrate_from_text,
    merge_adapted_experience,
    normalize_resume,
    resume_is_empty,
)
from app.services.scoring.llm import LLMConfig, LLMError


def test_flatten_resume_jobs_and_skills() -> None:
    text = flatten_resume(
        {
            "name": "Иван Петров",
            "headline": "Python backend",
            "email": "ivan@test",
            "skills": ["FastAPI", "Postgres"],
            "experience": [
                {
                    "company": "Acme",
                    "title": "Backend",
                    "period": "2022—2025",
                    "bullets": ["Собрал API", ""],
                }
            ],
        }
    )
    assert "Иван Петров" in text
    assert "FastAPI" in text
    assert "Acme" in text
    assert "Собрал API" in text


def test_hydrate_and_empty() -> None:
    doc = hydrate_from_text("Иван Петров\nPython, FastAPI, Postgres", None)
    assert doc["name"] == "Иван Петров"
    assert "FastAPI" in doc["summary"]
    assert resume_is_empty({})
    assert resume_is_empty(None)
    assert not resume_is_empty(doc)


def test_normalize_resume_coerces_strings() -> None:
    doc = normalize_resume({"skills": "Go, Python", "links": "https://x.test"})
    assert doc["skills"] == ["Go", "Python"]
    assert doc["links"] == ["https://x.test"]
    assert doc["skill_groups"][0]["items"] == "Go, Python"


def test_flatten_latex_shape() -> None:
    text = flatten_resume(
        {
            "name": "Дмитрий",
            "headline": "ML Engineer",
            "telegram": "@Fllarpy",
            "skill_groups": [{"label": "Python", "items": "FastAPI, AsyncIO"}],
            "experience": [
                {
                    "company": "MStroy",
                    "title": "ML Engineer",
                    "period": "2024 — 2026",
                    "context": "B2B SaaS",
                    "bullets": [
                        {
                            "text": "RAG и GraphRAG",
                            "children": ["гибридный пайплайн"],
                        }
                    ],
                }
            ],
        }
    )
    assert "Технические навыки" in text
    assert "Python: FastAPI" in text
    assert "MStroy" in text
    assert "гибридный пайплайн" in text


def test_session_header_opens_profile(client) -> None:
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    row = client.post(
        "/api/auth/register",
        json={"email": f"clip-{suffix}@hunt.test", "password": "password1"},
    )
    assert row.status_code == 200, row.text
    token = client.cookies["hunt_session"]
    client.cookies.clear()
    denied = client.get("/api/settings/profile")
    assert denied.status_code == 401
    ok = client.get("/api/settings/profile", headers={SESSION_HEADER: token})
    assert ok.status_code == 200, ok.text


def _cfg() -> LLMConfig:
    return LLMConfig(provider="openai", model="gpt-4o-mini", openai_api_key="sk-test", ollama_base_url="")


def test_fill_resume_skips_llm_without_key() -> None:
    doc = asyncio.run(fill_resume_from_text("Иван Петров\nPython, FastAPI", None, cfg=None))
    assert doc["name"] == "Иван Петров"
    assert "FastAPI" in doc["summary"]
    assert doc["experience"] == []


def test_fill_resume_uses_llm_json(monkeypatch) -> None:
    async def fake_complete(cfg, *, system, user, json_mode=True):
        assert "Huntos AI" in system
        assert "Иван" in user
        return json.dumps(
            {
                "name": "Иван Петров",
                "headline": "Python backend",
                "skills": ["FastAPI", "Postgres"],
                "skill_groups": [{"label": "Python", "items": "FastAPI, Postgres"}],
                "experience": [
                    {
                        "company": "Acme",
                        "title": "Backend",
                        "period": "2022—2025",
                        "bullets": [{"text": "Собрал API", "children": []}],
                    }
                ],
            }
        )

    monkeypatch.setattr("app.services.resume.complete", fake_complete)
    doc = asyncio.run(fill_resume_from_text("Иван, FastAPI", None, cfg=_cfg()))
    assert doc["name"] == "Иван Петров"
    assert doc["headline"] == "Python backend"
    assert doc["experience"][0]["company"] == "Acme"
    assert doc["experience"][0]["bullets"][0]["text"] == "Собрал API"


def test_fill_resume_falls_back_on_llm_error(monkeypatch) -> None:
    async def boom(cfg, *, system, user, json_mode=True):
        raise LLMError("no key")

    monkeypatch.setattr("app.services.resume.complete", boom)
    doc = asyncio.run(fill_resume_from_text("Мария Соколова\nGo, Kubernetes", None, cfg=_cfg()))
    assert doc["name"] == "Мария Соколова"
    assert "Kubernetes" in doc["summary"]


def test_merge_adapted_experience_keeps_jobs_rewrites_bullets() -> None:
    base = {
        "experience": [
            {
                "company": "Acme",
                "title": "Backend",
                "period": "2022—2025",
                "bullets": [{"text": "Писал API", "children": []}],
            },
            {
                "company": "Beta",
                "title": "Go",
                "period": "2021",
                "bullets": [{"text": "Сервисы", "children": []}],
            },
        ]
    }
    merged = merge_adapted_experience(
        base,
        [
            {
                "company": "Acme",
                "title": "Backend",
                "bullets": [{"text": "Писал API на FastAPI и PostgreSQL", "children": ["OpenAPI"]}],
            },
            {
                "company": "Invented Corp",
                "bullets": [{"text": "Выдумал опыт"}],
            },
        ],
    )
    jobs = merged["experience"]
    assert jobs[0]["period"] == "2022—2025"
    assert "FastAPI" in jobs[0]["bullets"][0]["text"]
    assert jobs[0]["bullets"][0]["children"] == ["OpenAPI"]
    assert jobs[1]["company"] == "Beta"
    assert jobs[1]["bullets"][0]["text"] == "Сервисы"
    assert len(jobs) == 2


def test_merge_adapted_experience_positional_fallback() -> None:
    merged = merge_adapted_experience(
        {"experience": [{"company": "Acme", "title": "Dev", "bullets": ["старый"]}]},
        [{"bullets": ["новый буллет с Kafka"]}],
    )
    assert merged["experience"][0]["company"] == "Acme"
    assert merged["experience"][0]["bullets"][0]["text"] == "новый буллет с Kafka"


def test_save_resume_json_flattens_text(client) -> None:
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    client.post(
        "/api/auth/register",
        json={"email": f"cv-{suffix}@hunt.test", "password": "password1"},
    )
    saved = client.put(
        "/api/settings/profile",
        json={
            "resume_json": {
                "name": "Анна",
                "headline": "Go developer",
                "skills": ["Go", "Kubernetes"],
                "summary": "Пишу сервисы.",
            }
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["resume_json"]["name"] == "Анна"
    assert "Kubernetes" in (data["resume_text"] or "")


def test_public_cv_requires_opt_in_and_share_token(client) -> None:
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    email = f"pub-{suffix}@hunt.test"
    client.post("/api/auth/register", json={"email": email, "password": "password1"})
    saved = client.put(
        "/api/settings/profile",
        json={"resume_json": {"name": "Игорь", "headline": "Go", "experience": [{"company": "Acme", "bullets": ["API"]}]}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["resume_public"] is False
    assert saved.json()["resume_share_id"] is None

    user_id = client.get("/api/auth/me").json()["id"]
    client.cookies.clear()
    leaked = client.get(f"/api/public/cv/{user_id}")
    assert leaked.status_code == 404

    login = client.post("/api/auth/login", json={"email": email, "password": "password1"})
    assert login.status_code == 200, login.text
    published = client.put("/api/settings/profile", json={"resume_public": True})
    assert published.status_code == 200, published.text
    assert published.json()["resume_public"] is True
    share_id = published.json()["resume_share_id"]
    assert share_id

    client.cookies.clear()
    row = client.get(f"/api/public/cv/{share_id}")
    assert row.status_code == 200, row.text
    assert row.json()["resume"]["name"] == "Игорь"
    assert row.json()["adapted"] is False
    assert "user_id" not in row.json()
    missing = client.get("/api/public/cv/not-a-real-token")
    assert missing.status_code == 404

    login = client.post("/api/auth/login", json={"email": email, "password": "password1"})
    assert login.status_code == 200, login.text
    closed = client.put("/api/settings/profile", json={"resume_public": False})
    assert closed.status_code == 200, closed.text
    assert closed.json()["resume_public"] is False
    assert closed.json()["resume_share_id"] == share_id
    client.cookies.clear()
    hidden = client.get(f"/api/public/cv/{share_id}")
    assert hidden.status_code == 404
