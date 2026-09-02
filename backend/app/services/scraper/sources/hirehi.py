from __future__ import annotations

import html as html_lib
import re
from urllib.parse import parse_qs, urlencode, urlparse

from app.services.company_icon import normalize_company_icon
from app.services.scraper.http import PoliteHttp
from app.services.scraper.salary import parse_salary

HIREHI_ORIGIN = "https://hirehi.ru"

_CYR_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "io",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ы": "y",
    "э": "e",
    "ю": "iu",
    "я": "ia",
}


def slugify_title(title: str) -> str:
    """Match HireHi public URLs: /{category}/{slug}-{id}."""
    slug = "".join(_CYR_TO_LAT.get(ch, ch) for ch in (title or "").lower())
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug


def job_page_url(*, category: str | None, title: str, job_id: str | int) -> str:
    cat = (category or "development").strip("/") or "development"
    slug = slugify_title(title) or "vacancy"
    return f"{HIREHI_ORIGIN}/{cat}/{slug}-{job_id}"


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_listing_url(url: str) -> dict:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    category = parts[1] if len(parts) >= 2 and parts[0] == "vacancies" else "development"

    def first(name: str, default: str = "") -> str:
        values = qs.get(name) or []
        return values[0] if values else default

    def many(name: str) -> list[str]:
        return qs.get(name) or []

    return {
        "category": first("category", category),
        "search": first("search"),
        "sort": first("sort", "date"),
        "format": many("format"),
        "level": many("level"),
        "subcategory": many("subcategory"),
        "english": many("english"),
        "country": many("country"),
        "region": many("region"),
        "industry": many("industry"),
        "direct_contact": many("direct_contact"),
        "salary": many("salary"),
        "city": first("city"),
    }


def listing_url_from_params(params: dict) -> str:
    category = params.get("category") or "development"
    query: list[tuple[str, str]] = []
    for key, value in params.items():
        if key in {"category", "sort"}:
            continue
        if isinstance(value, list):
            for item in value:
                if item:
                    query.append((key, str(item)))
        elif value:
            query.append((key, str(value)))
    encoded = urlencode(query, doseq=True)
    path = f"{HIREHI_ORIGIN}/vacancies/{category}"
    return f"{path}?{encoded}" if encoded else path


def _repeat_params(params: dict, page: int, limit: int) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = [
        ("page", str(page)),
        ("limit", str(limit)),
        ("sort", str(params.get("sort") or "date")),
        ("category", str(params.get("category") or "development")),
        ("include_counts", "false"),
    ]
    search = params.get("search")
    if search:
        pairs.append(("search", str(search)))
    city = params.get("city")
    if city:
        pairs.append(("city", str(city)))
    for key in (
        "format",
        "level",
        "salary",
        "direct_contact",
        "english",
        "hirehi",
        "industry",
        "country",
        "region",
        "subcategory",
    ):
        values = params.get(key) or []
        if isinstance(values, str):
            values = [values]
        for item in values:
            if item:
                pairs.append((key, str(item)))
    return pairs


def _build_tags(detail: dict, skills: list[str]) -> list[str]:
    tags: list[str] = []
    for key in ("level", "format", "language", "category"):
        value = detail.get(key)
        if value:
            tags.append(str(value))
    tags.extend(skills)
    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        normalized = tag.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique[:24]


def normalize_job(detail: dict, listing_item: dict | None = None) -> dict:
    data = {**(listing_item or {}), **detail}
    skills = data.get("skills_list") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    salary_raw = data.get("salary_display") or data.get("salary")
    salary_min, salary_max, currency = parse_salary(salary_raw)
    description = strip_html(data.get("description_details") or data.get("description"))
    requirements = strip_html(data.get("requirements_details") or data.get("requirements"))
    tasks = strip_html(data.get("tasks_details"))
    conditions = strip_html(data.get("conditions_details"))
    parts = [p for p in (description, tasks, requirements, conditions) if p]
    category = data.get("category") or "development"
    source_id = str(data["id"])
    return {
        "source": "hirehi",
        "source_id": source_id,
        "source_url": job_page_url(category=category, title=data.get("title") or "Untitled", job_id=source_id),
        "title": data.get("title") or "Untitled",
        "company": data.get("company"),
        "company_icon": normalize_company_icon(data.get("company_icon"), page_url=HIREHI_ORIGIN),
        "grade": data.get("level"),
        "work_format": data.get("format"),
        "category": category,
        "industry": data.get("industry"),
        "location": data.get("location") or None,
        "country": data.get("country"),
        "region": data.get("region"),
        "language": data.get("language"),
        "salary_raw": salary_raw,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency or "RUB",
        "description": "\n\n".join(parts),
        "requirements": requirements,
        "tasks_html": data.get("tasks_details"),
        "conditions_html": data.get("conditions_details"),
        "important_info": data.get("important_info_text"),
        "skills": skills,
        "tags": _build_tags(data, skills),
        "raw_payload": data,
        "published_at": data.get("created_at"),
    }


async def backfill_job_page_urls(session) -> int:
    """Rewrite listing URLs to the public job page. Safe to run on every startup."""
    from sqlalchemy import select

    from app.models.vacancy import Vacancy

    result = await session.execute(select(Vacancy).where(Vacancy.source == "hirehi"))
    changed = 0
    for vacancy in result.scalars():
        url = job_page_url(category=vacancy.category, title=vacancy.title, job_id=vacancy.source_id)
        if vacancy.source_url != url:
            vacancy.source_url = url
            changed += 1
    if changed:
        await session.commit()
    return changed


class HireHiSource:
    name = "hirehi"

    def __init__(self, http: PoliteHttp | None = None) -> None:
        self.http = http or PoliteHttp()

    async def search(self, query_params: dict, *, page: int, limit: int = 20) -> dict:
        params = _repeat_params(query_params, page=page, limit=limit)
        referer = listing_url_from_params(query_params)
        return await self.http.get_json(
            f"{HIREHI_ORIGIN}/api/search/jobs",
            params=params,
            referer=referer,
        )

    async def detail(self, job_id: str | int, query_params: dict | None = None) -> dict:
        referer = listing_url_from_params(query_params or {"category": "development"})
        return await self.http.get_json(
            f"{HIREHI_ORIGIN}/api/jobs/{job_id}",
            referer=referer,
        )

    def normalize(self, detail: dict, listing_item: dict | None = None) -> dict:
        return normalize_job(detail, listing_item)
