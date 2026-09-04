from __future__ import annotations

import hashlib
import re
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donor_cache import DonorListing
from app.models.vacancy import PipelineStage, ScoringStatus, Vacancy
from app.services.company_icon import hydrate_company_icon, normalize_company_icon
from app.services.scraper.engine import upsert_donor_listing, upsert_vacancy
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.salary import parse_salary

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
_HABR = re.compile(r"career\.habr\.com/vacancies/(\d+)", re.I)
_GETMATCH = re.compile(r"getmatch\.ru/vacancies/(\d+)", re.I)
_GEEKJOB = re.compile(r"geekjob\.ru/vacancy/([0-9a-f]{24})", re.I)
_AVIASALES = re.compile(r"aviasales\.ru/(?:about/)?vacancies/(\d+)", re.I)
_VK = re.compile(r"team\.vk\.company/vacancy/(\d+)", re.I)
_YANDEX = re.compile(r"yandex\.ru/jobs/(?:vacancies/([^/?#]+)|api/publications/(\d+))", re.I)
_AVITO = re.compile(r"career\.avito\.(?:com|ru)/vacancies/([^/]+)/(\d+)", re.I)
_KASPERSKY = re.compile(r"careers\.kaspersky\.ru/vacancy/(\d+)", re.I)
_YADRO = re.compile(r"careers\.yadro\.com/vacancy/(\d+)", re.I)
_MEGAFON = re.compile(r"job\.megafon\.ru/vacancy/([^/?#]+)", re.I)
_SOLAR = re.compile(r"team\.rt-solar\.ru/vacancies/(\d+)", re.I)
_SELECTEL = re.compile(r"selectel\.ru/careers/all/vacancy/(\d+)", re.I)
_X5 = re.compile(
    r"x5(?:-tech\.ru|\.tech)/vacancy/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)
_ITONE = re.compile(r"it-one\.ru/vacancies/([0-9a-f]{16,})", re.I)
_CLOUDRU = re.compile(r"cloud\.ru/career/vacancies/(\d+)", re.I)
_CROC = re.compile(r"careers\.croc\.ru/vacancies/([a-z0-9-]+)", re.I)
_JET = re.compile(r"jet\.su/career/vacancies/([a-z0-9-]+)", re.I)
_MTS = re.compile(r"job\.mts\.ru/vacancy/(\d+)", re.I)
_IBS = re.compile(r"ibs\.ru/career/jobs/([a-z0-9-]+)", re.I)
_TGIS = re.compile(r"job\.2gis\.ru/vacancies/[a-z0-9_]+/(\d+)", re.I)
_ALFA = re.compile(r"job\.alfabank\.ru/vacancies/(.+?)/?(?:$|[?#])", re.I)
_KONTUR = re.compile(r"kontur\.ru/career/vacancies/(\d+)", re.I)
_WB = re.compile(r"career\.(?:wb|rwb)\.ru/vacancy/(\d+)", re.I)
_TBANK = re.compile(
    r"(?:tbank|tinkoff)\.ru/career/it/vacancy/[^/]+/([^/]+)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)
_TITLE = re.compile(r"<title[^>]*>([^<]+)", re.I)
_OG_TITLE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_OG_TITLE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:title["\']',
    re.I,
)

KNOWN_BOARDS = {"hh", "hirehi", "habr", "getmatch", "geekjob", "career"}


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
    habr = _HABR.search(text)
    if habr:
        return "habr", habr.group(1)
    getmatch = _GETMATCH.search(text)
    if getmatch:
        return "getmatch", getmatch.group(1)
    geekjob = _GEEKJOB.search(text)
    if geekjob:
        return "geekjob", geekjob.group(1).lower()
    aviasales = _AVIASALES.search(text)
    if aviasales:
        return "career", f"aviasales:{aviasales.group(1)}"
    vk = _VK.search(text)
    if vk:
        return "career", f"vk:{vk.group(1)}"
    yandex = _YANDEX.search(text)
    if yandex:
        local = yandex.group(2) or yandex.group(1)
        return "career", f"yandex:{local}"
    avito = _AVITO.search(text)
    if avito:
        return "career", f"avito:{avito.group(1)}/{avito.group(2)}"
    kaspersky = _KASPERSKY.search(text)
    if kaspersky:
        return "career", f"kaspersky:{kaspersky.group(1)}"
    yadro = _YADRO.search(text)
    if yadro:
        return "career", f"yadro:{yadro.group(1)}"
    megafon = _MEGAFON.search(text)
    if megafon:
        return "career", f"megafon:1/{megafon.group(1)}"
    solar = _SOLAR.search(text)
    if solar:
        return "career", f"solar:{solar.group(1)}"
    selectel = _SELECTEL.search(text)
    if selectel:
        return "career", f"selectel:{selectel.group(1)}"
    x5 = _X5.search(text)
    if x5:
        return "career", f"x5:{x5.group(1).lower()}"
    itone = _ITONE.search(text)
    if itone:
        return "career", f"itone:{itone.group(1).lower()}"
    cloudru = _CLOUDRU.search(text)
    if cloudru:
        return "career", f"cloudru:{cloudru.group(1)}"
    croc = _CROC.search(text)
    if croc and croc.group(1) not in {"", "vacancies"}:
        return "career", f"croc:{croc.group(1).lower()}"
    jet = _JET.search(text)
    if jet and jet.group(1) not in {"", "vacancies"}:
        return "career", f"jet:{jet.group(1).lower()}"
    mts = _MTS.search(text)
    if mts:
        return "career", f"mts:{mts.group(1)}"
    ibs = _IBS.search(text)
    if ibs and ibs.group(1) not in {"filter", "jobs"}:
        return "career", f"ibs:{ibs.group(1).lower()}"
    tgis = _TGIS.search(text)
    if tgis:
        return "career", f"2gis:{tgis.group(1)}"
    alfa = _ALFA.search(text)
    if alfa:
        slug = alfa.group(1).strip("/").lower()
        tail = re.search(r"_(\d+)$", slug)
        if tail:
            return "career", f"alfa:{tail.group(1)}"
        if slug.isdigit():
            return "career", f"alfa:{slug}"
    kontur = _KONTUR.search(text)
    if kontur:
        return "career", f"kontur:{kontur.group(1)}"
    wb = _WB.search(text)
    if wb:
        return "career", f"wb:{wb.group(1)}"
    tbank = _TBANK.search(text)
    if tbank:
        return "career", f"tbank:{tbank.group(1)}/{tbank.group(2).lower()}"
    if text:
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        return "clip", digest
    return "clip", hashlib.sha256(b"empty").hexdigest()[:16]


def extract_html(html: str, *, page_url: str | None = None) -> dict[str, str]:
    out = extract_job_posting(html, page_url=page_url)
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
    source, source_id = detect_source(page_url)
    incoming = {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "description": (description or "").strip(),
        "salary_raw": (salary_raw or "").strip(),
        "company_icon": "",
    }
    cached = None
    if source in KNOWN_BOARDS and source_id:
        cached = (
            await session.execute(
                select(DonorListing).where(
                    DonorListing.source == source, DonorListing.source_id == source_id
                )
            )
        ).scalar_one_or_none()
        if cached and cached.payload:
            payload = dict(cached.payload)
            for key in ("title", "company", "description"):
                if incoming.get(key) and not payload.get(key):
                    payload[key] = incoming[key]
            vacancy, action = await upsert_vacancy(
                session, payload, scraper_config_id=None, user_id=user_id
            )
            if action != "new":
                _fill_vacancy(vacancy, incoming)
                await hydrate_company_icon(session, vacancy)
            return vacancy, action

    if page_url and (not incoming["title"] or not incoming["description"]):
        fetched = await fetch_page(page_url)
        for key, value in fetched.items():
            if not incoming.get(key):
                incoming[key] = value

    if not incoming["title"] and not incoming["description"] and not page_url:
        raise ValueError("Нужен URL или текст вакансии")

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
    if source in KNOWN_BOARDS and payload.get("source_id"):
        await upsert_donor_listing(session, payload)
        await session.commit()
    if action != "new":
        _fill_vacancy(vacancy, incoming)
        await hydrate_company_icon(session, vacancy)
    return vacancy, action
