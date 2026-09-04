"""GeekJob search — qs= plus the same listing filters as company boards."""

from __future__ import annotations

from urllib.parse import urlencode

from app.services.scraper.sources.career_filters import STACK_IDS, career_job_matches
from app.services.scraper.sources.geo import CITY_IDS

GEEKJOB_ORIGIN = "https://geekjob.ru"


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _as_int(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def normalize_geekjob_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    out: dict = {"search": str(data.get("search") or data.get("q") or data.get("qs") or "").strip()}
    formats = [item for item in _as_list(data.get("formats") or data.get("format")) if item in ("remote", "office", "hybrid")]
    if formats:
        out["formats"] = sorted(set(formats))
    levels = [
        item
        for item in _as_list(data.get("levels") or data.get("level"))
        if item in ("intern", "junior", "middle", "senior", "lead", "head")
    ]
    if levels:
        out["levels"] = sorted(set(levels))
    stack = [item for item in _as_list(data.get("stack")) if item in STACK_IDS]
    if stack:
        out["stack"] = sorted(set(stack))
    cities = [item for item in _as_list(data.get("cities") or data.get("city")) if item in CITY_IDS]
    if cities:
        out["cities"] = sorted(set(cities))
    if data.get("only_salary") or data.get("onlySalary"):
        out["only_salary"] = True
    salary = _as_int(data.get("salary_from") or data.get("salaryFrom") or data.get("salary"))
    if salary:
        out["salary_from"] = salary
    if data.get("remote"):
        formats = list(out.get("formats") or [])
        if "remote" not in formats:
            formats.append("remote")
        out["formats"] = sorted(set(formats))
    return out


def qs_from_params(params: dict) -> str:
    data = normalize_geekjob_params(params)
    parts = [data.get("search") or ""]
    parts.extend(data.get("stack") or [])
    return " ".join(str(part).strip() for part in parts if str(part).strip())


def listing_url_from_params(params: dict, *, page: int = 1) -> str:
    qs = qs_from_params(params)
    query: dict[str, str] = {}
    if qs:
        query["qs"] = qs
    if page > 1:
        query["page"] = str(page)
    if not query:
        return f"{GEEKJOB_ORIGIN}/"
    return f"{GEEKJOB_ORIGIN}/?{urlencode(query)}"


def auto_name(params: dict) -> str:
    data = normalize_geekjob_params(params)
    parts: list[str] = []
    if data.get("search"):
        parts.append(str(data["search"]))
    stack = data.get("stack") or []
    if len(stack) >= max(8, len(STACK_IDS) - 4):
        parts.append("весь IT")
    else:
        for key in stack:
            parts.append(str(key))
    formats = data.get("formats") or []
    if formats and len(formats) < 3:
        labels = {"remote": "удалённо", "office": "офис", "hybrid": "гибрид"}
        parts.extend(labels.get(item, item) for item in formats)
    unique = list(dict.fromkeys(parts))
    return " · ".join(unique[:5]) or "GeekJob поиск"


def geekjob_job_matches(job: dict, params: dict | None) -> bool:
    data = normalize_geekjob_params(params)
    return career_job_matches(job, {"company": "vk", **data})
