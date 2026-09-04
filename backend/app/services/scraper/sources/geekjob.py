from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

from app.services.company_icon import normalize_company_icon
from app.services.scraper.http import PoliteHttp
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.geekjob_filters import (
    GEEKJOB_ORIGIN,
    geekjob_job_matches,
    listing_url_from_params,
)
from app.services.scraper.sources.hirehi import strip_html

_VACANCY_ID = re.compile(r"/vacancy/([0-9a-f]{24})(?:/|$|[?#])", re.I)
_CARD = re.compile(r"<li\b([^>]*)>(.*?)</li>", re.I | re.S)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)
_TITLE = re.compile(r"""class=["'][^"']*title[^"']*["'][^>]*>(.*?)</a>""", re.I | re.S)
_COMPANY = re.compile(r"""company-name[^>]*>[\s\S]*?<a[^>]*>(.*?)</a>""", re.I)
_LOGO = re.compile(r"""<img[^>]+class=["'][^"']*vacancy-list-logo[^"']*["'][^>]+src=["']([^"']+)["']""", re.I)
_LOGO_REV = re.compile(r"""<img[^>]+src=["']([^"']+)["'][^>]+class=["'][^"']*vacancy-list-logo""", re.I)


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", strip_html(text))).strip()


def parse_search_html(html: str) -> list[dict]:
    """Cards from geekjob.ru listing. Ads without /vacancy/{hex} are skipped."""
    jobs: list[dict] = []
    seen: set[str] = set()
    for _attrs, body in _CARD.findall(html or ""):
        vacancy_href = ""
        source_id = ""
        for href in _HREF.findall(body):
            match = _VACANCY_ID.search(href)
            if match:
                vacancy_href = href
                source_id = match.group(1).lower()
                break
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        title_m = _TITLE.search(body)
        title = _clean(title_m.group(1) if title_m else "")
        company_m = _COMPANY.search(body)
        company = _clean(company_m.group(1) if company_m else "")
        if company and title.lower() == company.lower():
            title = ""
        if not title:
            plain = _clean(re.sub(r"<img[^>]*>", " ", body, flags=re.I))
            bits = [bit.strip() for bit in re.split(r"\n+", plain) if bit.strip()]
            title = next((bit for bit in bits if bit.lower() != (company or "").lower()), "") or "Untitled"
        logo_m = _LOGO.search(body) or _LOGO_REV.search(body)
        logo = logo_m.group(1) if logo_m else ""
        url = urljoin(GEEKJOB_ORIGIN + "/", vacancy_href)
        jobs.append(
            {
                "id": source_id,
                "title": title or "Untitled",
                "company": company or None,
                "company_icon": urljoin(GEEKJOB_ORIGIN, logo) if logo else None,
                "source_url": url,
            }
        )
    if jobs:
        return jobs
    for match in _VACANCY_ID.finditer(html or ""):
        source_id = match.group(1).lower()
        if source_id in seen:
            continue
        seen.add(source_id)
        jobs.append(
            {
                "id": source_id,
                "title": "Untitled",
                "source_url": f"{GEEKJOB_ORIGIN}/vacancy/{source_id}",
            }
        )
    return jobs


_PAGE_HREF = re.compile(r"""[?&]page=(\d+)""", re.I)
_REL_NEXT = re.compile(r"""rel=["']next["']""", re.I)


def listing_has_more(html: str, *, page: int, raw_count: int) -> bool:
    want = page + 1
    for raw in _PAGE_HREF.findall(html or ""):
        try:
            if int(raw) >= want:
                return True
        except ValueError:
            continue
    if _REL_NEXT.search(html or ""):
        return True
    return raw_count >= 15


def _grade_from_text(*parts: str) -> str | None:
    blob = " ".join(parts).lower()
    for grade in ("lead", "senior", "middle", "junior", "intern"):
        if grade in blob:
            return grade
    if "ведущ" in blob:
        return "lead"
    if "старш" in blob:
        return "senior"
    if "средн" in blob:
        return "middle"
    if "младш" in blob:
        return "junior"
    if "стажёр" in blob or "стажер" in blob:
        return "intern"
    return None


def normalize_geekjob_job(detail: dict, listing_item: dict | None = None) -> dict:
    data = {**(listing_item or {}), **detail}
    source_id = str(data.get("id") or data.get("source_id") or "").lower()
    url = data.get("source_url") or data.get("url") or f"{GEEKJOB_ORIGIN}/vacancy/{source_id}"
    skills = data.get("skills") or []
    if isinstance(skills, str):
        skills = [item.strip() for item in skills.split(",") if item.strip()]
    skills = [str(item).strip() for item in skills if str(item).strip()]
    description = strip_html(str(data.get("description") or ""))
    salary_raw = data.get("salary_raw") or data.get("salary")
    salary_min, salary_max, currency = parse_salary(salary_raw if isinstance(salary_raw, str) else None)
    remote = data.get("work_format") == "удалённо" or bool(data.get("remote"))
    if "телекоммут" in description.lower() or "удалён" in description.lower() or "удален" in description.lower():
        remote = True
    grade = data.get("grade") or _grade_from_text(str(data.get("title") or ""), description, " ".join(skills))
    tags: list[str] = ["geekjob"]
    if grade:
        tags.append(grade)
    if remote:
        tags.append("удалённо")
    tags.extend(skills)
    unique: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = str(tag).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(str(tag).strip())
    return {
        "source": "geekjob",
        "source_id": source_id,
        "source_url": url,
        "title": data.get("title") or "Untitled",
        "company": data.get("company"),
        "company_icon": normalize_company_icon(data.get("company_icon"), page_url=url or GEEKJOB_ORIGIN),
        "grade": grade,
        "work_format": "удалённо" if remote else data.get("work_format"),
        "category": "development",
        "location": data.get("location"),
        "salary_raw": salary_raw if isinstance(salary_raw, str) else None,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency or "RUB",
        "description": description or None,
        "requirements": description or None,
        "skills": skills,
        "tags": unique[:24],
        "raw_payload": data,
        "published_at": data.get("published_at") or data.get("datePosted"),
    }


class GeekJobSource:
    name = "geekjob"

    def __init__(self, http: PoliteHttp | None = None) -> None:
        self.http = http or PoliteHttp()

    async def search(self, query_params: dict, *, page: int, limit: int = 50) -> dict:
        html = await self.http.get_text(
            listing_url_from_params(query_params, page=page),
            referer=GEEKJOB_ORIGIN + "/",
        )
        raw = parse_search_html(html)
        jobs = [job for job in raw if geekjob_job_matches(job, query_params)]
        has_more = listing_has_more(html, page=page, raw_count=len(raw))
        return {"jobs": jobs[:limit] if limit else jobs, "has_more": has_more, "total_count": len(raw)}

    async def detail(self, job_id: str | int, query_params: dict | None = None) -> dict:
        source_id = str(job_id).strip().lower()
        url = f"{GEEKJOB_ORIGIN}/vacancy/{source_id}"
        html = await self.http.get_text(url, referer=listing_url_from_params(query_params or {}))
        posted = extract_job_posting(html, page_url=url)
        return {"id": source_id, "source_url": url, **posted}

    def normalize(self, detail: dict, listing_item: dict | None = None) -> dict:
        return normalize_geekjob_job(detail, listing_item)
