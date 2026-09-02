from __future__ import annotations

import hashlib
import json
import re
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import PipelineStage, ScoringStatus, Vacancy
from app.services.company_icon import hydrate_company_icon, logo_from_hiring_org, normalize_company_icon
from app.services.scraper.engine import upsert_vacancy
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.hirehi import strip_html

TRACKING = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ysclid",
    "yclid",
}

_HH = re.compile(r"(?:hh\.ru|rabota\.by|hh\.kz|hh1\.az)/vacancy/(\d+)", re.I)
_HIREHI = re.compile(r"hirehi\.ru/[^/?#]+/.+-(\d+)/?(?:$|[?#])", re.I)
_TITLE = re.compile(r"<title[^>]*>([^<]+)", re.I)
_OG_TITLE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_OG_TITLE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:title["\']',
    re.I,
)
_JSONLD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)

TRACKING = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ysclid",
    "yclid",
}

_HH = re.compile(r"(?:hh\.ru|rabota\.by|hh\.kz|hh1\.az)/vacancy/(\d+)", re.I)
_HIREHI = re.compile(r"hirehi\.ru/[^/?#]+/.+-(\d+)/?(?:$|[?#])", re.I)
_TITLE = re.compile(r"<title[^>]*>([^<]+)", re.I)
_OG_TITLE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_OG_TITLE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:title["\']',
    re.I,
)
_JSONLD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)


def canonical_url(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return None
    if host.endswith(".local") or host.endswith(".internal"):
        return None
    if re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host):
        return None
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING]
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", urlencode(query), "")
    )


def detect_source(url: str | None) -> tuple[str, str]:
    text = url or ""
    hh = _HH.search(text)
    if hh:
        return "hh", hh.group(1)
    hirehi = _HIREHI.search(text)
    if hirehi:
        return "hirehi", hirehi.group(1)
    if text:
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        return "clip", digest
    return "clip", hashlib.sha256(b"empty").hexdigest()[:16]


def _first_job_posting(node: object) -> dict | None:
    if isinstance(node, list):
        for item in node:
            found = _first_job_posting(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None
    types = node.get("@type")
    labels = types if isinstance(types, list) else [types]
    if any(str(label).lower() == "jobposting" for label in labels if label):
        return node
    graph = node.get("@graph")
    if graph is not None:
        return _first_job_posting(graph)
    return None


def extract_html(html: str, *, page_url: str | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    for script in _JSONLD.findall(html or ""):
        try:
            data = json.loads(unescape(script))
        except json.JSONDecodeError:
            continue
        job = _first_job_posting(data)
        if not job:
            continue
        title = str(job.get("title") or "").strip()
        org = job.get("hiringOrganization")
        company = ""
        if isinstance(org, dict):
            company = str(org.get("name") or "").strip()
            logo = logo_from_hiring_org(org, page_url=page_url)
            if logo:
                out["company_icon"] = logo
        elif isinstance(org, str):
            company = org.strip()
        description = strip_html(str(job.get("description") or ""))
        salary = job.get("baseSalary")
        salary_raw = ""
        if isinstance(salary, dict):
            value = salary.get("value")
            if isinstance(value, dict):
                lo = value.get("minValue") or value.get("value")
                hi = value.get("maxValue") or lo
                unit = value.get("unitText") or salary.get("currency") or ""
                salary_raw = " ".join(str(part) for part in (lo, hi, unit) if part)
            elif value is not None:
                salary_raw = str(value)
        if title:
            out["title"] = title[:512]
        if company:
            out["company"] = company[:255]
        if description:
            out["description"] = description[:20000]
        if salary_raw:
            out["salary_raw"] = salary_raw[:128]
        break
    if "title" not in out:
        og = _OG_TITLE.search(html or "") or _OG_TITLE_REV.search(html or "")
        title_tag = _TITLE.search(html or "")
        picked = (og.group(1) if og else "") or (title_tag.group(1) if title_tag else "")
        picked = unescape(re.sub(r"\s+", " ", picked)).strip()
        if picked:
            out["title"] = picked[:512]
    return out


async def fetch_page(url: str) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            ctype = (response.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text" not in ctype:
                return {}
            return extract_html(response.text[:400_000], page_url=str(response.url))
    except httpx.HTTPError:
        return {}


def _apply_salary(payload: dict, raw: str | None) -> None:
    text = (raw or "").strip()
    if not text:
        return
    payload["salary_raw"] = text[:128]
    lo, hi, currency = parse_salary(text)
    if lo is not None:
        payload["salary_min"] = lo
    if hi is not None:
        payload["salary_max"] = hi
    if currency:
        payload["salary_currency"] = currency


def _fill_vacancy(vacancy: Vacancy, incoming: dict) -> bool:
    changed = False
    title = (incoming.get("title") or "").strip()
    if title and (not (vacancy.title or "").strip() or vacancy.title == "Новая вакансия"):
        vacancy.title = title[:512]
        changed = True
    desc = (incoming.get("description") or "").strip()
    have = (vacancy.description or "").strip()
    if desc and (not have or len(desc) > len(have) + 80):
        vacancy.description = desc[:20000]
        changed = True
    company = (incoming.get("company") or "").strip()
    if company and not (vacancy.company or "").strip():
        vacancy.company = company[:255]
        changed = True
    if incoming.get("salary_raw") and not vacancy.salary_raw:
        _apply_salary({"salary_raw": incoming["salary_raw"]}, incoming["salary_raw"])
        vacancy.salary_raw = incoming["salary_raw"][:128]
        lo, hi, currency = parse_salary(incoming["salary_raw"])
        vacancy.salary_min = vacancy.salary_min or lo
        vacancy.salary_max = vacancy.salary_max or hi
        vacancy.salary_currency = vacancy.salary_currency or currency
        changed = True
    icon = normalize_company_icon(incoming.get("company_icon"), page_url=vacancy.source_url)
    if icon and not normalize_company_icon(vacancy.company_icon, page_url=vacancy.source_url):
        vacancy.company_icon = icon
        changed = True
    if changed and vacancy.pipeline_stage == PipelineStage.INBOX:
        vacancy.scoring_status = ScoringStatus.PENDING
        vacancy.match_score = None
    return changed


async def clip_vacancy(
    session: AsyncSession,
    user_id: int,
    *,
    url: str | None,
    title: str | None,
    company: str | None,
    description: str | None,
    salary_raw: str | None,
) -> tuple[Vacancy, str]:
    page_url = canonical_url(url)
    incoming = {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "description": (description or "").strip(),
        "salary_raw": (salary_raw or "").strip(),
        "company_icon": "",
    }
    if page_url and (not incoming["title"] or not incoming["description"]):
        fetched = await fetch_page(page_url)
        for key, value in fetched.items():
            if not incoming.get(key):
                incoming[key] = value

    if not incoming["title"] and not incoming["description"] and not page_url:
        raise ValueError("Нужен URL или текст вакансии")

    source, source_id = detect_source(page_url)
    if source == "clip" and not page_url:
        source_id = uuid4().hex[:16]

    payload: dict = {
        "source": source,
        "source_id": source_id,
        "source_url": page_url,
        "title": incoming["title"] or "Без названия",
        "company": incoming["company"] or None,
        "description": incoming["description"] or None,
        "skills": [],
        "tags": [source],
    }
    _apply_salary(payload, incoming.get("salary_raw"))
    icon = normalize_company_icon(incoming.get("company_icon"), page_url=page_url)
    if icon:
        payload["company_icon"] = icon
    payload = {key: value for key, value in payload.items() if value not in (None, "")}

    if page_url:
        by_url = (
            await session.execute(
                select(Vacancy).where(
                    Vacancy.user_id == user_id,
                    Vacancy.source_url == page_url,
                    Vacancy.duplicate_of_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if by_url is not None:
            _fill_vacancy(by_url, incoming)
            await hydrate_company_icon(session, by_url)
            return by_url, "merged"

    vacancy, action = await upsert_vacancy(session, payload, scraper_config_id=None, user_id=user_id)
    if action != "new":
        _fill_vacancy(vacancy, incoming)
        await hydrate_company_icon(session, vacancy)
    return vacancy, action
