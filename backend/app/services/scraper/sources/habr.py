from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape

from app.services.company_icon import normalize_company_icon
from app.services.scraper.http import PoliteHttp
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.habr_filters import (
    HABR_ORIGIN,
    api_url_from_params,
    listing_url_from_params,
    rss_url_from_params,
)
from app.services.scraper.sources.hirehi import strip_html

_TITLE_QUOTE = re.compile(r"«([^»]+)»")
_HASH = re.compile(r"#([^\s,#.]+)")


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1].lower() if "}" in tag else tag.lower()


def _text(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return unescape(node.text).strip()


def _child(item: ET.Element, name: str) -> ET.Element | None:
    for child in item:
        if _local(child.tag) == name:
            return child
    return None


def parse_search_rss(xml_text: str) -> list[dict]:
    """RSS items from career.habr.com/vacancies/rss."""
    root = ET.fromstring(xml_text)
    jobs: list[dict] = []
    for item in root.iter():
        if _local(item.tag) != "item":
            continue
        guid = _text(_child(item, "guid"))
        link = _text(_child(item, "link"))
        title_raw = _text(_child(item, "title"))
        quoted = _TITLE_QUOTE.search(title_raw)
        title = quoted.group(1).strip() if quoted else title_raw
        description = _text(_child(item, "description"))
        company = _text(_child(item, "author"))
        if not company:
            m = re.search(r"Компания «([^»]+)»", description)
            company = m.group(1) if m else ""
        source_id = guid or (re.search(r"/vacancies/(\d+)", link).group(1) if re.search(r"/vacancies/(\d+)", link) else "")
        if not source_id:
            continue
        image = _text(_child(item, "image"))
        skills = [unescape(tag) for tag in _HASH.findall(description)]
        jobs.append(
            {
                "id": source_id,
                "title": title or title_raw or "Untitled",
                "company": company or None,
                "company_icon": image or None,
                "source_url": link or f"{HABR_ORIGIN}/vacancies/{source_id}",
                "description": description,
                "skills": skills,
                "published_at": _text(_child(item, "pubdate")) or _text(_child(item, "pubDate")),
            }
        )
    return jobs


def parse_api_list(payload: dict) -> tuple[list[dict], bool]:
    """JSON from career.habr.com/api/frontend/vacancies."""
    jobs: list[dict] = []
    for item in payload.get("list") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id") or "").strip()
        if not source_id:
            continue
        company = item.get("company") if isinstance(item.get("company"), dict) else {}
        logo = ""
        if isinstance(company.get("logo"), dict):
            logo = str(company["logo"].get("src") or company["logo"].get("url") or "")
        elif isinstance(company.get("logo"), str):
            logo = company["logo"]
        skills_raw = item.get("skills") or []
        skills = [
            str(skill.get("title") or "").strip()
            for skill in skills_raw
            if isinstance(skill, dict) and str(skill.get("title") or "").strip()
        ]
        salary = item.get("salary") if isinstance(item.get("salary"), dict) else {}
        href = str(item.get("href") or f"/vacancies/{source_id}")
        url = href if href.startswith("http") else f"{HABR_ORIGIN}{href}"
        locations = item.get("locations") or []
        city = ", ".join(
            str(loc.get("title") or "").strip()
            for loc in locations
            if isinstance(loc, dict) and str(loc.get("title") or "").strip()
        )
        remote = bool(item.get("remoteWork"))
        jobs.append(
            {
                "id": source_id,
                "title": item.get("title") or "Untitled",
                "company": company.get("title") if isinstance(company, dict) else None,
                "company_icon": logo or None,
                "source_url": url,
                "skills": skills,
                "salary_raw": salary.get("formatted") if salary else None,
                "work_format": "удалённо" if remote else None,
                "remote": remote,
                "grade": str(item.get("qualification") or "").lower() or None,
                "location": city or None,
            }
        )
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    try:
        current = int(meta.get("currentPage") or 1)
        total = int(meta.get("totalPages") or 1)
    except (TypeError, ValueError):
        current, total = 1, 1
    if meta:
        has_more = current < total
    else:
        has_more = len(jobs) >= 20
    return jobs, has_more


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


def normalize_habr_job(detail: dict, listing_item: dict | None = None) -> dict:
    data = {**(listing_item or {}), **detail}
    source_id = str(data.get("id") or data.get("source_id") or "")
    url = data.get("source_url") or data.get("url") or f"{HABR_ORIGIN}/vacancies/{source_id}"
    skills = data.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    description = strip_html(data.get("description") or "")
    salary_raw = data.get("salary_raw") or data.get("salary")
    salary_min, salary_max, currency = parse_salary(salary_raw)
    remote = data.get("work_format") == "удалённо" or bool(data.get("remote"))
    if "можно удалённо" in (data.get("description") or "").lower() or "можно удаленно" in description.lower():
        remote = True
    grade = data.get("grade") or _grade_from_text(description, " ".join(skills), str(data.get("title") or ""))
    tags: list[str] = ["habr"]
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
        "source": "habr",
        "source_id": source_id,
        "source_url": url,
        "title": data.get("title") or "Untitled",
        "company": data.get("company"),
        "company_icon": normalize_company_icon(data.get("company_icon"), page_url=url or HABR_ORIGIN),
        "grade": grade,
        "work_format": "удалённо" if remote else data.get("work_format"),
        "category": "development",
        "location": data.get("location"),
        "salary_raw": salary_raw,
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


class HabrSource:
    name = "habr"

    def __init__(self, http: PoliteHttp | None = None) -> None:
        self.http = http or PoliteHttp()

    async def search(self, query_params: dict, *, page: int, limit: int = 25) -> dict:
        referer = listing_url_from_params(query_params)
        try:
            payload = await self.http.get_json(
                api_url_from_params(query_params, page=page, per_page=min(50, max(limit, 25))),
                referer=referer,
            )
            if isinstance(payload, dict) and (payload.get("list") is not None or payload.get("meta")):
                jobs, has_more = parse_api_list(payload)
                return {"jobs": jobs[:limit] if limit else jobs, "has_more": has_more, "total_count": len(jobs)}
        except Exception:
            pass
        xml_text = await self.http.get_text(
            rss_url_from_params(query_params, page=page),
            referer=referer,
            accept="application/rss+xml, application/xml, text/xml;q=0.9,*/*;q=0.8",
        )
        jobs = parse_search_rss(xml_text)
        has_more = len(jobs) >= 20
        return {"jobs": jobs[:limit] if limit else jobs, "has_more": has_more, "total_count": len(jobs)}

    async def detail(self, job_id: str | int, query_params: dict | None = None) -> dict:
        url = f"{HABR_ORIGIN}/vacancies/{job_id}"
        html = await self.http.get_text(url, referer=listing_url_from_params(query_params or {}))
        posted = extract_job_posting(html, page_url=url)
        return {"id": str(job_id), "source_url": url, **posted}

    def normalize(self, detail: dict, listing_item: dict | None = None) -> dict:
        return normalize_habr_job(detail, listing_item)
