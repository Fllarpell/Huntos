"""One adapter for company career sites. Catalog picks the parser."""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import parse_qs, urlparse

from app.services.company_icon import normalize_company_icon
from app.services.scraper.http import PoliteHttp
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.career_catalog import (
    AVITO_IT_SLUGS,
    CROC_IT_SECTIONS,
    IBS_IT_FILTERS,
    KASPERSKY_IT_CATEGORIES,
    MEGAFON_IT_SPECIALTIES,
    MTS_IT_CATEGORIES,
    TBANK_IT_CATEGORIES,
    TGIS_IT_DIRECTIONS,
    VK_IT_SPECIALTIES,
    WB_IT_DIRECTIONS,
    YADRO_IT_DIRECTION,
    CareerBoard,
    get_board,
)
from app.services.scraper.sources.career_filters import career_job_matches, normalize_career_params, yandex_professions
from app.services.scraper.sources.geo import tbank_city_slug
from app.services.scraper.sources.hirehi import strip_html

_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_TITLE = re.compile(r"<title[^>]*>([^<]+)", re.I)
_ROUTER = re.compile(r"window\._ROUTER_DATA\s*=\s*", re.I)
_VK_ARTICLE_OPEN = re.compile(r'<div[^>]*itemprop=["\']description["\'][^>]*>', re.I)
_VK_TITLE_PROP = re.compile(r'<div[^>]*itemprop=["\']title["\'][^>]*>(.*?)</div>', re.I | re.S)
_VK_FIELD_TITLE = re.compile(r'<h4 class="vacancy-title">(.*?)</h4>', re.I | re.S)
_VK_TAG = re.compile(r'<div class="vacancy-tag">(.*?)</div>', re.I | re.S)
_VK_FEATURE = re.compile(r'<div class="features-item-text">(.*?)</div>', re.I | re.S)
_VK_NOTICE = re.compile(
    r'<div class="notice-block">.*?<h2 class="title-block">(?P<name>.*?)</h2>.*?<div class="text-mid">(?P<body>.*?)</div>',
    re.I | re.S,
)
_AVITO_SECTION = re.compile(r'<section class="vacancies-detail__description">(.*?)</section>', re.I | re.S)
_SOLAR_CARD = re.compile(
    r'<a class="[^"]*vacancies__title"[^>]*href="/vacancies/(?P<id>\d+)/"[^>]*>(?P<title>.*?)</a>',
    re.I | re.S,
)
_SOLAR_BODY = re.compile(r'<div class="vacancies-details-body">(?P<body>.*?)</div>', re.I | re.S)
_SELECTEL_CARD = re.compile(
    r'<a href="/careers/all/vacancy/(?P<id>\d+)/"[^>]*card__link[^>]*>\s*'
    r'(?:<span[^>]*>.*?</span>\s*)?<h5[^>]*>(?P<title>.*?)</h5>\s*<p[^>]*>(?P<loc>.*?)</p>',
    re.I | re.S,
)
_ITONE_BODY = re.compile(
    r'<section class="article card">\s*<div class="content">\s*<div class="body">(?P<body>.*?)</div>\s*<div class="tags">',
    re.I | re.S,
)
_X5_HREF = re.compile(
    r'href=["\']/vacancy/(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})["\']',
    re.I,
)
_CLOUD_HREF = re.compile(r'href=["\']/career/vacancies/(?P<id>\d+)["\']', re.I)
_CROC_CARD = re.compile(
    r'class="vacancy__card-item[^"]*"[^>]*>\s*<a[^>]*href="/vacancies/(?P<slug>[a-z0-9][a-z0-9-]*)/"[^>]*>(?P<title>.*?)</a>',
    re.I | re.S,
)
_JET_CARD = re.compile(
    r'class="vacancies__vacancies-card"[^>]*href="/career/vacancies/(?P<slug>[a-z0-9-]+)/"[^>]*>(?P<title>.*?)</a>',
    re.I | re.S,
)
_IBS_JOB = re.compile(r'href="/career/jobs/(?P<slug>[a-z0-9-]+)/"', re.I)
_KONTUR_CARD = re.compile(
    r'href="/career/vacancies/(?P<id>\d+)"[^>]*>.*?class="vacancy__title">(?P<title>.*?)</span>.*?'
    r'class="vacancy__description">(?P<meta>.*?)</div>',
    re.I | re.S,
)
_ALFA_IT_TITLE = re.compile(
    r"разработ|developer|devops|engineer|\bqa\b|тестир|тест\b|архитект|\bsre\b|android|\bios\b|"
    r"\.net|\bc#\b|python|\bjava\b|golang|\bgo[- ]|backend|frontend|data engineer|data scientist|"
    r"\bml\b|machine learning|\bdba\b|\bsql\b|инженер|product owner|product manager|ux researcher|"
    r"ux.?design|ui.?design|системн.{0,6}аналит|devsecops|secops|appsec|информацион.{0,6}безопас",
    re.I,
)
_KONTUR_IT_TITLE = _ALFA_IT_TITLE
_LISTING_JUNK = {
    "вакансии",
    "vacancies",
    "смотреть все",
    "стажировки",
    "фильтр",
    "ещё",
    "все вакансии",
    "открытые вакансии",
}
_JOB_JUNK_LINE = re.compile(
    r"^(откликнуться|больше вакансий|похожие вакансии|подробнее о проекте|©\s*\d{4}.*)$",
    re.I,
)

YANDEX_API = "https://yandex.ru/jobs/api/publications/"
VK_API = "https://team.vk.company/career/api/v2/vacancies/"
TBANK_API = "https://www.tbank.ru/pfpjobs/papi/getVacancies"
YADRO_API = "https://careers.yadro.com/api/vacancies"
MEGAFON_API = "https://job.megafon.ru/api/v1/vacancies"
ITONE_API = "https://www.it-one.ru/api/entities/vacancy"
ITONE_TAKE = 50
ITONE_CAP = 250
X5_PAGES = 8
JET_PAGES = 8
MTS_API = "https://job.mts.ru/api/v2/vacancies"
MTS_PAGE = 50
MTS_CAP = 300
TGIS_API = "https://job.2gis.ru/api/v1/vacancies"
TGIS_PAGE = 50
TGIS_CAP = 300
ALFA_API = "https://job.alfabank.ru/api/vacancies"
ALFA_PAGE = 200
ALFA_CAP = 400
WB_API = "https://career.rwb.ru/crm-api/api/v1/pub/vacancies"
WB_PAGE = 50
WB_CAP = 400
TBANK_PAGE = 50
TBANK_CAP = 250
MOSCOW_FIAS = "0c5b2444-70a0-4932-980c-b4dc0d3f02b5"


def career_id(slug: str, local: str | int) -> str:
    return f"{slug}:{local}"


def split_career_id(job_id: str | int, fallback_slug: str = "") -> tuple[str, str]:
    text = str(job_id).strip()
    if ":" in text:
        slug, local = text.split(":", 1)
        return slug.strip().lower(), local.strip()
    return (fallback_slug or "").strip().lower(), text


def _tag_inner(html: str, open_re: re.Pattern[str]) -> str:
    match = open_re.search(html or "")
    if not match:
        return ""
    tag_m = re.match(r"<(\w+)", match.group(0), re.I)
    if not tag_m:
        return ""
    tag = tag_m.group(1)
    start = match.end()
    depth = 1
    for found in re.finditer(rf"<\s*(/)?{tag}\b[^>]*>", html, re.I):
        if found.start() < start:
            continue
        if found.group(1):
            depth -= 1
            if depth == 0:
                return html[start : found.start()]
        else:
            depth += 1
    return html[start:]


def _job_text(html_fragment: str) -> str:
    lines: list[str] = []
    for raw in strip_html(html_fragment).splitlines():
        line = raw.strip()
        if not line or _JOB_JUNK_LINE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _unique_texts(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _vk_fields(html: str) -> list[str]:
    titles = list(_VK_FIELD_TITLE.finditer(html))
    fields: list[str] = []
    for index, match in enumerate(titles):
        end = titles[index + 1].start() if index + 1 < len(titles) else len(html)
        window = html[match.end() : end]
        for cutter in ("notice-block", "Похожие вакансии", 'class="features"', "<footer"):
            cut = window.find(cutter)
            if cut >= 0:
                window = window[:cut]
        label = strip_html(match.group(1))
        tags = _unique_texts([strip_html(item) for item in _VK_TAG.findall(window)])
        if label and tags:
            fields.append(f"{label}: {', '.join(tags)}")
    return fields


def _json_after(html: str, marker: re.Pattern[str]) -> dict | None:
    match = marker.search(html or "")
    if not match:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode((html or "")[match.end() :].lstrip())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _loader_blob(data: dict, key_part: str) -> dict:
    loader = data.get("loaderData")
    if not isinstance(loader, dict):
        return {}
    for key, value in loader.items():
        if key_part in str(key).replace("\\", "/") and isinstance(value, dict):
            return value
    return {}


def parse_aviasales_listing(html: str) -> list[dict]:
    data = _json_after(html, _ROUTER)
    if not data:
        return []
    blob = _loader_blob(data, "about/vacancies/page")
    rows = blob.get("vacancies") if isinstance(blob.get("vacancies"), list) else []
    jobs: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        local = str(row["id"])
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        jobs.append(
            {
                "id": career_id("aviasales", local),
                "title": row.get("position") or "Untitled",
                "company": "Авиасейлс",
                "company_icon": team.get("icon"),
                "skills": row.get("tags") if isinstance(row.get("tags"), list) else [],
                "location": row.get("workPlace"),
                "source_url": f"https://www.aviasales.ru/about/vacancies/{local}",
                "team": team.get("name"),
            }
        )
    return jobs


def parse_aviasales_detail(html: str, job_id: str) -> dict:
    data = _json_after(html, _ROUTER) or {}
    blob = _loader_blob(data, "about/vacancies/(id)/page")
    vacancy = blob.get("vacancy") if isinstance(blob.get("vacancy"), dict) else {}
    local = str(vacancy.get("id") or split_career_id(job_id, "aviasales")[1])
    team = vacancy.get("team") if isinstance(vacancy.get("team"), dict) else {}
    parts = [
        vacancy.get("description") or "",
        vacancy.get("todo") or "",
        vacancy.get("requirements") or "",
        vacancy.get("conditions") or "",
    ]
    description = strip_html("\n\n".join(part for part in parts if part))
    skills = vacancy.get("tags") if isinstance(vacancy.get("tags"), list) else []
    specs = vacancy.get("specializations") if isinstance(vacancy.get("specializations"), list) else []
    skills = [str(item) for item in [*skills, *specs] if item]
    return {
        "id": career_id("aviasales", local),
        "title": vacancy.get("position") or "Untitled",
        "company": "Авиасейлс",
        "company_icon": team.get("icon"),
        "description": description,
        "requirements": strip_html(str(vacancy.get("requirements") or "")),
        "skills": skills,
        "location": vacancy.get("workPlace"),
        "source_url": f"https://www.aviasales.ru/about/vacancies/{local}",
        "team": team.get("name"),
    }


def parse_vk_listing(payload: dict) -> list[dict]:
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    jobs: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        spec = row.get("specialty") if isinstance(row.get("specialty"), dict) else {}
        spec_id = spec.get("id")
        try:
            spec_n = int(spec_id) if spec_id is not None else 0
        except (TypeError, ValueError):
            spec_n = 0
        if spec_n not in VK_IT_SPECIALTIES:
            continue
        local = str(row["id"])
        town = row.get("town") if isinstance(row.get("town"), dict) else {}
        group = row.get("group") if isinstance(row.get("group"), dict) else {}
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        jobs.append(
            {
                "id": career_id("vk", local),
                "title": row.get("title") or "Untitled",
                "company": group.get("name") or "VK",
                "company_icon": group.get("project_logo"),
                "location": town.get("name"),
                "work_format": row.get("work_format"),
                "remote": bool(row.get("remote")),
                "skills": [str(tag.get("name") or "") for tag in tags if isinstance(tag, dict) and tag.get("name")],
                "specialty": spec.get("name"),
                "source_url": f"https://team.vk.company/vacancy/{local}/",
            }
        )
    return jobs


def parse_vk_detail_html(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "vk")[1]
    title_m = _TITLE.search(html or "")
    title_raw = unescape(title_m.group(1)).strip() if title_m else ""
    prop_title = strip_html(_VK_TITLE_PROP.search(html or "").group(1) if _VK_TITLE_PROP.search(html or "") else "")
    h1_m = _H1.search(html or "")
    h1 = strip_html(h1_m.group(1) if h1_m else "")
    title = prop_title or h1 or re.sub(r"^Вакансия\s+", "", title_raw, flags=re.I).strip() or "Untitled"
    article = _job_text(_tag_inner(html or "", _VK_ARTICLE_OPEN))
    fields = _vk_fields(html or "")
    perks = _unique_texts([strip_html(item) for item in _VK_FEATURE.findall(html or "")])
    notice = _VK_NOTICE.search(html or "")
    project = ""
    if notice and len(article) < 280:
        body = _job_text(notice.group("body"))
        name = strip_html(notice.group("name"))
        if body:
            project = f"{name}\n{body}" if name else body
    parts = [article, "\n".join(fields)]
    if perks:
        parts.append("Мы предлагаем\n" + "\n".join(f"- {item}" for item in perks))
    if project:
        parts.append(project)
    description = "\n\n".join(part for part in parts if part).strip()[:12000]
    location = None
    if "," in title:
        tail = title.rsplit(",", 1)[-1].strip()
        if tail and len(tail) < 40:
            location = tail
    return {
        "id": career_id("vk", local),
        "title": title,
        "company": "VK",
        "description": description,
        "location": location,
        "source_url": f"https://team.vk.company/vacancy/{local}/",
    }


def parse_yandex_listing(payload: dict) -> list[dict]:
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    jobs: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        local = str(row["id"])
        vacancy = row.get("vacancy") if isinstance(row.get("vacancy"), dict) else {}
        cities = vacancy.get("cities") if isinstance(vacancy.get("cities"), list) else []
        skills = vacancy.get("skills") if isinstance(vacancy.get("skills"), list) else []
        modes = vacancy.get("work_modes") if isinstance(vacancy.get("work_modes"), list) else []
        service = row.get("public_service") if isinstance(row.get("public_service"), dict) else {}
        slug = row.get("publication_slug_url") or local
        jobs.append(
            {
                "id": career_id("yandex", local),
                "title": row.get("title") or "Untitled",
                "company": service.get("name") or "Яндекс",
                "location": ", ".join(str(city.get("name") or "") for city in cities if isinstance(city, dict) and city.get("name")),
                "work_format": ", ".join(str(mode.get("name") or "") for mode in modes if isinstance(mode, dict) and mode.get("name")),
                "skills": [str(skill.get("name") or "") for skill in skills if isinstance(skill, dict) and skill.get("name")],
                "short_summary": row.get("short_summary") or "",
                "source_url": f"https://yandex.ru/jobs/vacancies/{slug}",
            }
        )
    return jobs


def parse_yandex_detail(payload: dict, job_id: str) -> dict:
    local = str(payload.get("id") or split_career_id(job_id, "yandex")[1])
    vacancy = payload.get("vacancy") if isinstance(payload.get("vacancy"), dict) else {}
    cities = vacancy.get("cities") if isinstance(vacancy.get("cities"), list) else []
    skills = vacancy.get("skills") if isinstance(vacancy.get("skills"), list) else []
    modes = vacancy.get("work_modes") if isinstance(vacancy.get("work_modes"), list) else {}
    if not isinstance(modes, list):
        modes = []
    service = payload.get("public_service") if isinstance(payload.get("public_service"), dict) else {}
    slug = payload.get("publication_slug_url") or local
    parts = [
        payload.get("description") or "",
        payload.get("duties") or "",
        payload.get("key_qualifications") or "",
        payload.get("conditions") or "",
        payload.get("short_summary") or "",
    ]
    description = strip_html("\n\n".join(str(part) for part in parts if part))
    return {
        "id": career_id("yandex", local),
        "title": payload.get("title") or "Untitled",
        "company": service.get("name") or "Яндекс",
        "description": description,
        "requirements": strip_html(str(payload.get("key_qualifications") or "")),
        "location": ", ".join(str(city.get("name") or "") for city in cities if isinstance(city, dict) and city.get("name")),
        "work_format": ", ".join(str(mode.get("name") or "") for mode in modes if isinstance(mode, dict) and mode.get("name")),
        "skills": [str(skill.get("name") or "") for skill in skills if isinstance(skill, dict) and skill.get("name")],
        "source_url": f"https://yandex.ru/jobs/vacancies/{slug}",
        "salary_raw": payload.get("salary") or payload.get("salary_raw"),
    }


_AVITO_CARD = re.compile(
    r'<div class="vacancies-section__item"\s+(?P<attrs>[^>]+)>\s*'
    r'<a href="(?P<href>/vacancies/(?P<cat>[^/]+)/(?P<id>\d+)/)" class="vacancies-section__item-link"></a>\s*'
    r'<div class="vacancies-section__item-content">\s*'
    r'<a href="[^"]+" class="vacancies-section__item-name">(?P<title>.*?)</a>',
    re.I | re.S,
)
_AVITO_ATTR = re.compile(r'data-vacancy-(?P<key>[\w-]+)="(?P<value>[^"]*)"', re.I)
_KASP_LINK = re.compile(r'<a[^>]+href="(/vacancy/(\d+))"[^>]*>(.*?)</a>', re.I | re.S)
_KASP_CAT = re.compile(r"vacancy-tag-category-(\d+)", re.I)
_KASP_CITY = re.compile(r"vacancy-tag-city-\d+[^>]*>(.*?)</", re.I | re.S)
_TBANK_HREF = re.compile(
    r"/career/it/vacancy/(?P<city>[^/]+)/(?P<seo>[^/]+)/(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/",
    re.I,
)


def _json_at(html: str, needle: str) -> dict | None:
    idx = (html or "").find(needle)
    if idx < 0:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode((html or "")[idx:])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_avito_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _AVITO_CARD.finditer(html or ""):
        cat = match.group("cat").strip().lower()
        if cat not in AVITO_IT_SLUGS:
            continue
        local = match.group("id")
        key = f"{cat}/{local}"
        if key in seen:
            continue
        seen.add(key)
        attrs = {item.group("key"): unescape(item.group("value")) for item in _AVITO_ATTR.finditer(match.group("attrs"))}
        remote_raw = (attrs.get("remote") or "").strip().lower()
        jobs.append(
            {
                "id": career_id("avito", key),
                "title": unescape(re.sub(r"\s+", " ", match.group("title"))).strip() or "Untitled",
                "company": "Авито",
                "location": attrs.get("geo"),
                "team": attrs.get("team"),
                "specialty": attrs.get("section") or cat,
                "remote": remote_raw in {"да", "yes", "true", "1"},
                "source_url": f"https://career.avito.com/vacancies/{cat}/{local}/",
            }
        )
    return jobs


def parse_avito_detail(html: str, job_id: str) -> dict:
    _slug, local = split_career_id(job_id, "avito")
    cat, _, num = local.partition("/")
    if not num:
        num = cat
        cat = "razrabotka"
    url = f"https://career.avito.com/vacancies/{cat}/{num}/"
    posted = extract_job_posting(html, page_url=url)
    sections = [_job_text(chunk) for chunk in _AVITO_SECTION.findall(html or "")]
    description = "\n\n".join(part for part in sections if part) or posted.get("description") or ""
    return {
        "id": career_id("avito", f"{cat}/{num}"),
        "title": posted.get("title") or "Untitled",
        "company": posted.get("company") or "Авито",
        "company_icon": posted.get("company_icon"),
        "description": description,
        "location": posted.get("location"),
        "work_format": posted.get("work_format"),
        "salary_raw": posted.get("salary_raw"),
        "published_at": posted.get("published_at"),
        "source_url": url,
    }


def parse_kaspersky_listing(html: str, *, category_id: int | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    expected = category_id if category_id in KASPERSKY_IT_CATEGORIES else None
    for match in _KASP_LINK.finditer(html or ""):
        local = match.group(2)
        if local in seen:
            continue
        title = strip_html(match.group(3))
        if not title or title.lower() in {"вакансии", "vacancies", "все вакансии"}:
            continue
        window = (html or "")[match.start() : match.start() + 1200]
        cat_m = _KASP_CAT.search(window)
        try:
            cat_n = int(cat_m.group(1)) if cat_m else (expected or 0)
        except (TypeError, ValueError):
            cat_n = expected or 0
        if expected is not None:
            cat_n = expected
        if cat_n not in KASPERSKY_IT_CATEGORIES:
            continue
        seen.add(local)
        city_m = _KASP_CITY.search(window)
        jobs.append(
            {
                "id": career_id("kaspersky", local),
                "title": title,
                "company": "Лаборатория Касперского",
                "location": strip_html(city_m.group(1)) if city_m else None,
                "specialty": str(cat_n),
                "source_url": f"https://careers.kaspersky.ru/vacancy/{local}",
            }
        )
    return jobs


def parse_kaspersky_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "kaspersky")[1]
    title_m = re.search(r'data-testid="vacancy-title"[^>]*>(.*?)</', html or "", re.I | re.S)
    h1_m = _H1.search(html or "")
    title = strip_html((title_m.group(1) if title_m else "") or (h1_m.group(1) if h1_m else "")) or "Untitled"
    body_m = re.search(
        r'data-testid="vacancy-body"[^>]*>(.*?)</div>\s*<div\s+data-testid=',
        html or "",
        re.I | re.S,
    )
    if not body_m:
        body_m = re.search(r'data-testid="vacancy-body"[^>]*>(.*)$', html or "", re.I | re.S)
    description = strip_html(body_m.group(1) if body_m else "")[:12000]
    city_m = _KASP_CITY.search(html or "")
    skills = [
        strip_html(item)
        for item in re.findall(r'data-testid="vacancy-tag-skill-\d+"[^>]*>(.*?)</', html or "", re.I | re.S)
    ]
    skills = [item for item in skills if item]
    return {
        "id": career_id("kaspersky", local),
        "title": title,
        "company": "Лаборатория Касперского",
        "description": description,
        "location": strip_html(city_m.group(1)) if city_m else None,
        "skills": skills,
        "source_url": f"https://careers.kaspersky.ru/vacancy/{local}",
    }


def _tbank_is_it(category: object) -> bool:
    text = str(category or "").strip().lower()
    return text in TBANK_IT_CATEGORIES or text.endswith("_it") or text == "it"


def _tbank_city_slug(subtitle: object, region_id: object) -> str:
    slug = tbank_city_slug(subtitle)
    if slug:
        return slug
    if str(region_id or "").strip().lower() == MOSCOW_FIAS:
        return "moscow"
    return "moscow"


def _tbank_location(row: dict) -> str | None:
    subtitle = str(row.get("subtitle") or "").strip()
    if subtitle:
        return subtitle
    cities = row.get("cities")
    if isinstance(cities, list):
        names = [str(item).strip() for item in cities if str(item).strip()]
        if names:
            return ", ".join(names)
    if str(row.get("regionId") or "").strip().lower() == MOSCOW_FIAS:
        return "Москва"
    return None


def parse_tbank_rows(rows: object, *, hrefs: dict | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    href_map = hrefs or {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if not _tbank_is_it(row.get("category")):
            continue
        uuid = str(row.get("urlSlug") or row.get("vacancyId") or "").strip().lower()
        if not uuid or uuid in seen:
            continue
        seen.add(uuid)
        seo = str(row.get("seoSlug") or uuid).strip() or uuid
        href = href_map.get(uuid)
        city = href.group("city") if href else _tbank_city_slug(row.get("subtitle"), row.get("regionId"))
        seo = href.group("seo") if href else seo
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        tag_text = [str(tag) if not isinstance(tag, dict) else str(tag.get("text") or "") for tag in tags]
        remote = any("удал" in item.lower() or "remote" in item.lower() for item in tag_text)
        jobs.append(
            {
                "id": career_id("tbank", f"{seo}/{uuid}"),
                "title": row.get("title") or "Untitled",
                "company": "Т-Банк",
                "location": _tbank_location(row),
                "short_summary": row.get("shortDescription") or "",
                "salary_raw": row.get("salary") if isinstance(row.get("salary"), str) else None,
                "skills": [item for item in tag_text if item],
                "remote": remote,
                "work_format": ", ".join(item for item in tag_text if item),
                "source_url": f"https://www.tbank.ru/career/it/vacancy/{city}/{seo}/{uuid}/",
            }
        )
    return jobs


def parse_tbank_api_payload(payload: dict | None) -> list[dict]:
    data = payload if isinstance(payload, dict) else {}
    blob = data.get("payload") if isinstance(data.get("payload"), dict) else data
    rows = blob.get("vacancies") if isinstance(blob, dict) else None
    return parse_tbank_rows(rows)


def tbank_next_offset(payload: dict | None, current: int) -> int | None:
    data = payload if isinstance(payload, dict) else {}
    blob = data.get("payload") if isinstance(data.get("payload"), dict) else data
    pagination = blob.get("nextPagination") if isinstance(blob, dict) else None
    it = pagination.get("it") if isinstance(pagination, dict) else None
    if not isinstance(it, dict):
        return None
    if it.get("isFinished"):
        return None
    try:
        offset = int(it.get("offset"))
    except (TypeError, ValueError):
        return None
    if offset <= current:
        return None
    return offset


def parse_tbank_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    data = _json_at(html or "", '{"stores":{') or {}
    stores = data.get("stores") if isinstance(data.get("stores"), dict) else {}
    blob = stores.get("vacanciesStore") if isinstance(stores.get("vacanciesStore"), dict) else {}
    rows = blob.get("vacancies") if isinstance(blob.get("vacancies"), list) else []
    hrefs = {item.group("uuid").lower(): item for item in _TBANK_HREF.finditer(html or "")}
    jobs = parse_tbank_rows(rows, hrefs=hrefs)
    seen = {str(job.get("id") or "").rsplit("/", 1)[-1].lower() for job in jobs}
    for match in _TBANK_HREF.finditer(html or ""):
        uuid = match.group("uuid").lower()
        if uuid in seen:
            continue
        seen.add(uuid)
        seo = unescape(match.group("seo"))
        city = match.group("city")
        jobs.append(
            {
                "id": career_id("tbank", f"{seo}/{uuid}"),
                "title": seo.replace("-", " "),
                "company": "Т-Банк",
                "source_url": f"https://www.tbank.ru/career/it/vacancy/{city}/{seo}/{uuid}/",
            }
        )
    return jobs


def parse_tbank_detail(html: str, job_id: str) -> dict:
    _slug, local = split_career_id(job_id, "tbank")
    seo, _, uuid = local.partition("/")
    if not uuid:
        uuid = seo
        seo = uuid
    data = _json_at(html or "", '{"stores":{') or {}
    stores = data.get("stores") if isinstance(data.get("stores"), dict) else {}
    blob = stores.get("vacancyDescriptionStore") if isinstance(stores.get("vacancyDescriptionStore"), dict) else {}
    desc = blob.get("vacancyDescription") if isinstance(blob.get("vacancyDescription"), dict) else {}
    uuid = str(desc.get("vacancyId") or desc.get("urlSlug") or uuid).strip().lower()
    seo = str(desc.get("seoSlug") or seo or uuid)
    blocks = desc.get("description") if isinstance(desc.get("description"), list) else []
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        parts.append(str(block.get("title") or ""))
        parts.append(str(block.get("content") or ""))
    description = strip_html("\n\n".join(part for part in parts if part))
    tags = desc.get("tags") if isinstance(desc.get("tags"), list) else []
    tag_text = [str(tag.get("text") or "") if isinstance(tag, dict) else str(tag) for tag in tags]
    salary = desc.get("salary")
    href = _TBANK_HREF.search(html or "")
    city = href.group("city") if href else "moscow"
    return {
        "id": career_id("tbank", f"{seo}/{uuid}"),
        "title": desc.get("title") or "Untitled",
        "company": "Т-Банк",
        "description": description,
        "skills": [item for item in tag_text if item],
        "work_format": ", ".join(item for item in tag_text if item),
        "salary_raw": salary if isinstance(salary, str) else None,
        "source_url": f"https://www.tbank.ru/career/it/vacancy/{city}/{seo}/{uuid}/",
    }


def _named(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("title") or "").strip()
    if isinstance(value, list):
        names = [_named(item) for item in value]
        return ", ".join(item for item in names if item)
    return str(value or "").strip()


def parse_yadro_listing(payload: dict | list | None) -> list[dict]:
    rows = payload.get("vacancies") if isinstance(payload, dict) else payload
    jobs: list[dict] = []
    if not isinstance(rows, list):
        return jobs
    for item in rows:
        if not isinstance(item, dict):
            continue
        direction = item.get("direction") if isinstance(item.get("direction"), dict) else {}
        if direction.get("id") != YADRO_IT_DIRECTION:
            continue
        local = str(item.get("id") or "").strip()
        if not local:
            continue
        loc_names = [_named(part) for part in (item.get("location") if isinstance(item.get("location"), list) else [])]
        loc_names = [name for name in loc_names if name]
        city = ", ".join(loc_names) if loc_names else None
        skills = [_named(part) for part in (item.get("skill") if isinstance(item.get("skill"), list) else [])]
        skills = [name for name in skills if name]
        empl = _named(item.get("empl"))
        grade = _named(item.get("grade"))
        jobs.append(
            {
                "id": career_id("yadro", local),
                "title": item.get("title") or "Untitled",
                "company": "YADRO",
                "description": strip_html(str(item.get("description") or "")),
                "location": city,
                "work_format": empl or None,
                "grade": grade or None,
                "skills": skills,
                "specialty": _named(item.get("specialization")) or None,
                "source_url": f"https://careers.yadro.com/vacancy/{local}",
            }
        )
    return jobs


def parse_yadro_detail(payload: dict | list | None, job_id: str) -> dict:
    local = split_career_id(job_id, "yadro")[1]
    rows = payload.get("vacancies") if isinstance(payload, dict) else payload
    if isinstance(rows, list):
        for item in rows:
            if isinstance(item, dict) and str(item.get("id") or "") == local:
                jobs = parse_yadro_listing({"vacancies": [item]})
                if jobs:
                    return jobs[0]
    return {"id": career_id("yadro", local), "company": "YADRO", "source_url": f"https://careers.yadro.com/vacancy/{local}"}


def parse_megafon_listing(payload: dict | None) -> list[dict]:
    rows = payload.get("vacancies") if isinstance(payload, dict) else None
    jobs: list[dict] = []
    if not isinstance(rows, list):
        return jobs
    for item in rows:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        city = item.get("city") if isinstance(item.get("city"), dict) else {}
        city_id = city.get("id") or 1
        tag = item.get("tag") if isinstance(item.get("tag"), dict) else {}
        specs = item.get("specialties") if isinstance(item.get("specialties"), list) else []
        jobs.append(
            {
                "id": career_id("megafon", f"{city_id}/{slug}"),
                "title": item.get("title") or "Untitled",
                "company": "МегаФон",
                "location": city.get("title"),
                "work_format": tag.get("title") or tag.get("code"),
                "skills": [str(spec) for spec in specs if spec],
                "source_url": f"https://job.megafon.ru/vacancy/{slug}",
            }
        )
    return jobs


def parse_megafon_detail(payload: dict | None, job_id: str) -> dict:
    _slug, local = split_career_id(job_id, "megafon")
    city_id, _, slug = local.partition("/")
    if not slug:
        slug = city_id
        city_id = "1"
    data = payload if isinstance(payload, dict) else {}
    city = data.get("city") if isinstance(data.get("city"), dict) else {}
    skills = []
    for item in data.get("keySkills") if isinstance(data.get("keySkills"), list) else []:
        if isinstance(item, dict) and item.get("title"):
            skills.append(str(item["title"]))
    specs = data.get("specialties") if isinstance(data.get("specialties"), list) else []
    skills.extend(str(spec) for spec in specs if spec)
    parts = [
        strip_html(str(data.get("description") or "")),
        strip_html(str(data.get("requirements") or "")),
        strip_html(str(data.get("conditions") or "")),
    ]
    salary_min = data.get("minSalary")
    salary_max = data.get("maxSalary")
    salary_raw = None
    if salary_min or salary_max:
        salary_raw = " ".join(
            part
            for part in (
                f"от {salary_min}" if salary_min else "",
                f"до {salary_max}" if salary_max else "",
            )
            if part
        )
    return {
        "id": career_id("megafon", f"{city.get('id') or city_id}/{data.get('slug') or slug}"),
        "title": data.get("title") or "Untitled",
        "company": "МегаФон",
        "description": "\n\n".join(part for part in parts if part),
        "location": city.get("title"),
        "work_format": data.get("workingSchedule"),
        "skills": _unique_texts(skills),
        "salary_raw": salary_raw,
        "source_url": f"https://job.megafon.ru/vacancy/{data.get('slug') or slug}",
    }


def parse_solar_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _SOLAR_CARD.finditer(html or ""):
        local = match.group("id")
        if local in seen:
            continue
        title = strip_html(match.group("title"))
        if not title or title.lower() in {"вакансии компании", "вакансии"}:
            continue
        seen.add(local)
        window = (html or "")[max(0, match.start() - 500) : match.start()]
        loc_m = re.search(r'vacancies-information_location">\s*<p[^>]*>(.*?)</p>', window, re.I | re.S)
        jobs.append(
            {
                "id": career_id("solar", local),
                "title": title,
                "company": "Солар",
                "location": strip_html(loc_m.group(1)) if loc_m else None,
                "source_url": f"https://team.rt-solar.ru/vacancies/{local}/",
            }
        )
    return jobs


def parse_solar_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "solar")[1]
    h1 = _H1.search(html or "")
    body = _SOLAR_BODY.search(html or "")
    return {
        "id": career_id("solar", local),
        "title": strip_html(h1.group(1) if h1 else "") or "Untitled",
        "company": "Солар",
        "description": strip_html(body.group("body") if body else "")[:12000],
        "source_url": f"https://team.rt-solar.ru/vacancies/{local}/",
    }


def _nearby_title(html: str, pos: int) -> str:
    window = html[max(0, pos - 700) : pos]
    texts = [strip_html(chunk).strip() for chunk in re.findall(r">([^<]{3,160})<", window)]
    for text in reversed(texts):
        low = text.casefold().replace("ё", "е")
        if len(text) < 4 or low in _LISTING_JUNK or text.isdigit():
            continue
        if text.startswith("http") or text.startswith("/"):
            continue
        return text
    return ""


def parse_selectel_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _SELECTEL_CARD.finditer(html or ""):
        local = match.group("id")
        if local in seen:
            continue
        title = strip_html(match.group("title"))
        if not title:
            continue
        seen.add(local)
        loc = strip_html(match.group("loc"))
        jobs.append(
            {
                "id": career_id("selectel", local),
                "title": title,
                "company": "Selectel",
                "location": loc or None,
                "remote": any(token in loc.lower() for token in ("удал", "remote")) if loc else False,
                "source_url": f"https://selectel.ru/careers/all/vacancy/{local}/",
            }
        )
    return jobs


def parse_selectel_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "selectel")[1]
    return _detail_from_html(
        html,
        slug="selectel",
        local=local,
        company="Selectel",
        url=f"https://selectel.ru/careers/all/vacancy/{local}/",
    )


def parse_x5_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _X5_HREF.finditer(html or ""):
        local = match.group("id").lower()
        if local in seen:
            continue
        title = _nearby_title(html or "", match.start())
        if not title:
            continue
        seen.add(local)
        jobs.append(
            {
                "id": career_id("x5", local),
                "title": title,
                "company": "X5 Tech",
                "source_url": f"https://x5.tech/vacancy/{local}",
            }
        )
    return jobs


def parse_x5_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "x5")[1]
    return _detail_from_html(
        html,
        slug="x5",
        local=local,
        company="X5 Tech",
        url=f"https://x5.tech/vacancy/{local}",
    )


def parse_itone_listing(payload: object) -> list[dict]:
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        for key in ("items", "results", "data", "vacancies"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
    jobs: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("url") or "").strip()
        local = path.strip("/").rsplit("/", 1)[-1] or str(row.get("id") or "").strip()
        if not local or local in seen:
            continue
        seen.add(local)
        if not path.startswith("/"):
            path = f"/vacancies/{local}/"
        loc = str(row.get("city") or "").strip()
        jobs.append(
            {
                "id": career_id("itone", local),
                "title": row.get("name") or "Untitled",
                "company": "IT_ONE",
                "location": loc or None,
                "grade": row.get("position"),
                "specialty": row.get("specialization"),
                "short_summary": row.get("preview"),
                "remote": any(token in loc.lower() for token in ("remote", "удал")) if loc else False,
                "source_url": f"https://www.it-one.ru{path}",
            }
        )
    return jobs


def parse_itone_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "itone")[1]
    h1 = _H1.search(html or "")
    body = _ITONE_BODY.search(html or "")
    desc = _job_text(body.group("body") if body else "")
    if not desc:
        posted = extract_job_posting(html, page_url=f"https://www.it-one.ru/vacancies/{local}/")
        desc = posted.get("description") or ""
    tags = re.findall(r'<div class="tag">(.*?)</div>', html or "", re.I | re.S)
    loc = next((strip_html(item) for item in tags if strip_html(item)), None)
    return {
        "id": career_id("itone", local),
        "title": strip_html(h1.group(1) if h1 else "") or "Untitled",
        "company": "IT_ONE",
        "description": desc[:12000],
        "location": loc,
        "source_url": f"https://www.it-one.ru/vacancies/{local}/",
    }


def _listing_title(raw: str) -> str:
    text = strip_html(raw)
    for line in text.splitlines():
        line = line.strip()
        if line and line.lower() not in _LISTING_JUNK and not line.isdigit():
            return line
    return text.strip()


def parse_croc_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _CROC_CARD.finditer(html or ""):
        local = match.group("slug")
        if local in seen:
            continue
        title = _listing_title(match.group("title"))
        if not title:
            continue
        seen.add(local)
        window = (html or "")[max(0, match.start() - 400) : match.end() + 400]
        loc_m = re.search(r"(Москва|Санкт-Петербург|Удаленно|Удалённо|Remote)", window, re.I)
        jobs.append(
            {
                "id": career_id("croc", local),
                "title": title,
                "company": "КРОК",
                "location": loc_m.group(1) if loc_m else None,
                "remote": bool(loc_m and "удал" in loc_m.group(1).lower()),
                "source_url": f"https://careers.croc.ru/vacancies/{local}/",
            }
        )
    return jobs


def parse_croc_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "croc")[1]
    return _detail_from_html(
        html,
        slug="croc",
        local=local,
        company="КРОК",
        url=f"https://careers.croc.ru/vacancies/{local}/",
    )


def parse_jet_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _JET_CARD.finditer(html or ""):
        local = match.group("slug")
        if local in seen:
            continue
        title = _listing_title(match.group("title"))
        if not title:
            continue
        seen.add(local)
        window = (html or "")[max(0, match.start() - 400) : match.end() + 400]
        loc_m = re.search(r"(Москва|Санкт-Петербург|Екатеринбург|Новосибирск|Казань)", window, re.I)
        jobs.append(
            {
                "id": career_id("jet", local),
                "title": title,
                "company": "Инфосистемы Джет",
                "location": loc_m.group(1) if loc_m else None,
                "source_url": f"https://jet.su/career/vacancies/{local}/",
            }
        )
    return jobs


def parse_jet_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "jet")[1]
    return _detail_from_html(
        html,
        slug="jet",
        local=local,
        company="Инфосистемы Джет",
        url=f"https://jet.su/career/vacancies/{local}/",
    )


def _mts_local(row: dict) -> str:
    return str(row.get("mtsId") or row.get("slug") or row.get("id") or "").strip()


def _mts_it(row: dict) -> bool:
    slugs = {str(item.get("slug") or "").strip() for item in row.get("categories") or [] if isinstance(item, dict)}
    return bool(slugs & MTS_IT_CATEGORIES)


def _mts_salary(row: dict) -> str | None:
    low = row.get("salaryFrom") or row.get("salaryMin")
    high = row.get("salaryTo") or row.get("salaryMax")
    if low is None and high is None:
        return None
    if low and high:
        return f"{low}–{high}"
    return str(low or high)


def _mts_listing_item(row: dict) -> dict | None:
    local = _mts_local(row)
    title = str(row.get("title") or row.get("name") or "").strip()
    if not local or not title:
        return None
    region = row.get("region") if isinstance(row.get("region"), dict) else {}
    location = str(region.get("title") or "").strip() or None
    formats = [str(item.get("title") or "") for item in row.get("workFormats") or [] if isinstance(item, dict)]
    return {
        "id": career_id("mts", local),
        "title": title,
        "company": "МТС",
        "location": location,
        "work_format": _work_format(*formats) or None,
        "salary_raw": _mts_salary(row),
        "source_url": f"https://job.mts.ru/vacancy/{local}",
    }


def parse_mts_listing(payload: dict | list | None) -> list[dict]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    jobs: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not _mts_it(row):
            continue
        item = _mts_listing_item(row)
        if item is None:
            continue
        key = str(item["id"])
        if key in seen:
            continue
        seen.add(key)
        jobs.append(item)
    return jobs


def parse_mts_detail(payload: dict | list | None, job_id: str) -> dict:
    local = split_career_id(job_id, "mts")[1]
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, dict):
        data = {}
    title = str(data.get("name") or data.get("title") or "").strip() or "Untitled"
    region = data.get("region") if isinstance(data.get("region"), dict) else {}
    location = str(region.get("title") or "").strip() or None
    chunks: list[str] = []
    detail = data.get("detailText") if isinstance(data.get("detailText"), dict) else {}
    for key, label in (
        ("descriptionOfProject", "О проекте"),
        ("description", "Задачи"),
        ("requirements", "Требования"),
        ("conditions", "Условия"),
    ):
        text = strip_html(str(detail.get(key) or ""))
        if text:
            chunks.append(f"{label}:\n{text}")
    if not chunks:
        chunks.append(strip_html(str(data.get("description") or "")))
    return {
        "id": career_id("mts", local),
        "title": title,
        "company": "МТС",
        "description": "\n\n".join(part for part in chunks if part).strip()[:12000],
        "location": location,
        "work_format": _work_format(data.get("work_format"), " ".join(chunks)),
        "salary_raw": _mts_salary(data),
        "source_url": f"https://job.mts.ru/vacancy/{local}",
    }


def parse_ibs_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _IBS_JOB.finditer(html or ""):
        local = match.group("slug")
        if local.startswith("filter") or local in seen:
            continue
        seen.add(local)
        title = _nearby_title(html or "", match.start()) or local.replace("-", " ")
        jobs.append(
            {
                "id": career_id("ibs", local),
                "title": title,
                "company": "IBS",
                "source_url": f"https://ibs.ru/career/jobs/{local}/",
            }
        )
    return jobs


def parse_ibs_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "ibs")[1]
    return _detail_from_html(
        html,
        slug="ibs",
        local=local,
        company="IBS",
        url=f"https://ibs.ru/career/jobs/{local}/",
    )


def parse_cloudru_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _CLOUD_HREF.finditer(html or ""):
        local = match.group("id")
        if local in seen:
            continue
        title = _nearby_title(html or "", match.start())
        if not title:
            continue
        seen.add(local)
        jobs.append(
            {
                "id": career_id("cloudru", local),
                "title": title,
                "company": "Cloud.ru",
                "source_url": f"https://cloud.ru/career/vacancies/{local}",
            }
        )
    return jobs


def parse_cloudru_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "cloudru")[1]
    return _detail_from_html(
        html,
        slug="cloudru",
        local=local,
        company="Cloud.ru",
        url=f"https://cloud.ru/career/vacancies/{local}",
    )


def _2gis_salary(row: dict) -> str | None:
    low = row.get("salaryFrom")
    high = row.get("salaryTo")
    if low is None and high is None:
        return None
    if low and high:
        return f"{low}–{high}"
    return str(low or high)


def _2gis_listing_item(row: dict) -> dict | None:
    local = str(row.get("id") or "").strip()
    title = str(row.get("title") or "").strip()
    if not local or not title:
        return None
    direction = row.get("direction") if isinstance(row.get("direction"), dict) else {}
    section = str(direction.get("slug") or "vacancies").strip()
    city = row.get("city") if isinstance(row.get("city"), dict) else {}
    location = str(city.get("name") or "").strip() or None
    remote = bool(row.get("isRemote"))
    return {
        "id": career_id("2gis", local),
        "title": title,
        "company": "2ГИС",
        "location": location,
        "remote": remote,
        "work_format": "удалённо" if remote else None,
        "salary_raw": _2gis_salary(row),
        "source_url": f"https://job.2gis.ru/vacancies/{section}/{local}",
    }


def parse_dgis_listing(payload: dict | list | None) -> list[dict]:
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    jobs: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = _2gis_listing_item(row)
        if item is None:
            continue
        key = str(item["id"])
        if key in seen:
            continue
        seen.add(key)
        jobs.append(item)
    return jobs


def parse_dgis_detail(payload: dict | list | None, job_id: str) -> dict:
    local = split_career_id(job_id, "2gis")[1]
    row = payload if isinstance(payload, dict) else {}
    listing = _2gis_listing_item(row) or {}
    description = strip_html(str(row.get("description") or row.get("shortDescription") or ""))
    return {
        "id": career_id("2gis", local),
        "title": listing.get("title") or str(row.get("title") or "").strip() or "Untitled",
        "company": "2ГИС",
        "description": description[:12000],
        "location": listing.get("location"),
        "work_format": listing.get("work_format"),
        "salary_raw": listing.get("salary_raw"),
        "source_url": listing.get("source_url") or f"https://job.2gis.ru/vacancies/development/{local}",
    }


def _alfa_it(row: dict) -> bool:
    title = str(row.get("name") or row.get("title") or "")
    if not _ALFA_IT_TITLE.search(title):
        return False
    lowered = title.casefold()
    if any(token in lowered for token in ("продаж", "кассир", "курьер", "оператор call", "колл-центр")):
        return False
    return True


def _alfa_url(row: dict) -> str:
    slug = str(row.get("slug") or "").strip()
    if slug.startswith("/"):
        return f"https://job.alfabank.ru/vacancies{slug}"
    code = str(row.get("code") or row.get("id") or "").strip()
    return f"https://job.alfabank.ru/vacancies/{code}"


def _alfa_work_format(row: dict) -> str | None:
    for item in row.get("jobTypes") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("value") or item.get("title") or "")
        fmt = _work_format(text)
        if fmt:
            return fmt
    return _work_format(str(row.get("descriptionText") or row.get("description") or ""))


def _alfa_skills(row: dict) -> list[str]:
    skills: list[str] = []
    for item in row.get("tags") or []:
        if isinstance(item, dict):
            value = str(item.get("value") or "").strip()
            if value:
                skills.append(value)
    for group in row.get("specialties") or []:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip()
            if value and value.casefold() not in {"ит", "it"}:
                skills.append(value)
    return skills


def _alfa_listing_item(row: dict) -> dict | None:
    local = str(row.get("id") or "").strip()
    title = str(row.get("name") or row.get("title") or "").strip()
    if not local or not title or not _alfa_it(row):
        return None
    return {
        "id": career_id("alfa", local),
        "title": title,
        "company": "Альфа-Банк",
        "location": str(row.get("city") or "").strip() or None,
        "work_format": _alfa_work_format(row),
        "skills": _alfa_skills(row),
        "source_url": _alfa_url(row),
    }


def parse_alfa_listing(payload: dict | list | None) -> list[dict]:
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    jobs: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = _alfa_listing_item(row)
        if item is None:
            continue
        key = str(item["id"])
        if key in seen:
            continue
        seen.add(key)
        jobs.append(item)
    return jobs


def parse_alfa_detail(payload: dict | list | None, job_id: str) -> dict:
    local = split_career_id(job_id, "alfa")[1]
    row = payload if isinstance(payload, dict) else {}
    listing = _alfa_listing_item(row) or {}
    chunks: list[str] = []
    for label, key in (
        ("Описание", "descriptionText"),
        ("Задачи", "duties"),
        ("Требования", "requirements"),
        ("Условия", "conditions"),
    ):
        text = strip_html(str(row.get(key) or ""))
        if text:
            chunks.append(f"{label}:\n{text}")
    if not chunks:
        chunks.append(strip_html(str(row.get("description") or "")))
    return {
        "id": career_id("alfa", local),
        "title": listing.get("title") or str(row.get("name") or "").strip() or "Untitled",
        "company": "Альфа-Банк",
        "description": "\n\n".join(part for part in chunks if part).strip()[:12000],
        "requirements": strip_html(str(row.get("requirements") or "")) or None,
        "location": listing.get("location") or str(row.get("city") or "").strip() or None,
        "work_format": listing.get("work_format") or _alfa_work_format(row),
        "skills": listing.get("skills") or _alfa_skills(row),
        "source_url": listing.get("source_url") or _alfa_url(row),
    }


def parse_kontur_listing(html: str) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for match in _KONTUR_CARD.finditer(html or ""):
        local = match.group("id")
        if local in seen:
            continue
        title = _listing_title(match.group("title"))
        if not title or not _KONTUR_IT_TITLE.search(title):
            continue
        seen.add(local)
        meta = strip_html(match.group("meta"))
        jobs.append(
            {
                "id": career_id("kontur", local),
                "title": title,
                "company": "Контур",
                "location": meta.split("\n")[0].strip() if meta else None,
                "work_format": _work_format(meta),
                "source_url": f"https://kontur.ru/career/vacancies/{local}",
            }
        )
    return jobs


def parse_kontur_detail(html: str, job_id: str) -> dict:
    local = split_career_id(job_id, "kontur")[1]
    return _detail_from_html(
        html,
        slug="kontur",
        local=local,
        company="Контур",
        url=f"https://kontur.ru/career/vacancies/{local}",
    )


def _wb_payload_rows(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [row for row in data["items"] if isinstance(row, dict)]
        if isinstance(payload.get("items"), list):
            return [row for row in payload["items"] if isinstance(row, dict)]
    return []


def _wb_listing_item(row: dict) -> dict | None:
    local = str(row.get("id") or "").strip()
    title = str(row.get("name") or row.get("title") or "").strip()
    if not local or not title:
        return None
    location = str(row.get("city_title") or row.get("office_location_city_title") or "").strip() or None
    formats = [str(item.get("title") or "") for item in row.get("employment_types") or [] if isinstance(item, dict)]
    return {
        "id": career_id("wb", local),
        "title": title,
        "company": "Wildberries",
        "location": location,
        "work_format": _work_format(*formats) or None,
        "source_url": f"https://career.wb.ru/vacancy/{local}",
    }


def parse_wb_listing(payload: object) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for row in _wb_payload_rows(payload):
        item = _wb_listing_item(row)
        if item is None:
            continue
        key = str(item["id"])
        if key in seen:
            continue
        seen.add(key)
        jobs.append(item)
    return jobs


def _wb_detail_row(payload: object) -> dict:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload
    return {}


def parse_wb_detail(payload: object, job_id: str) -> dict:
    local = split_career_id(job_id, "wb")[1]
    row = _wb_detail_row(payload)
    listing = _wb_listing_item(row) or {}
    chunks: list[str] = []
    description = strip_html(str(row.get("description") or ""))
    if description:
        chunks.append(description)
    requirements = [str(item).strip() for item in row.get("requirements_arr") or [] if str(item).strip()]
    duties = [str(item).strip() for item in row.get("duties_arr") or [] if str(item).strip()]
    conditions = [str(item).strip() for item in row.get("conditions_arr") or [] if str(item).strip()]
    if duties:
        chunks.append("Задачи:\n" + "\n".join(f"- {item}" for item in duties))
    if requirements:
        chunks.append("Требования:\n" + "\n".join(f"- {item}" for item in requirements))
    if conditions:
        chunks.append("Условия:\n" + "\n".join(f"- {item}" for item in conditions))
    formats = [str(item.get("title") or "") for item in row.get("employment_types_list") or [] if isinstance(item, dict)]
    return {
        "id": career_id("wb", local),
        "title": listing.get("title") or str(row.get("name") or "").strip() or "Untitled",
        "company": "Wildberries",
        "description": "\n\n".join(chunks).strip()[:12000],
        "requirements": "\n".join(requirements)[:8000] if requirements else None,
        "location": listing.get("location"),
        "work_format": listing.get("work_format") or _work_format(*formats),
        "source_url": listing.get("source_url") or f"https://career.wb.ru/vacancy/{local}",
    }


def parse_ozon_listing(html: str) -> list[dict]:
    del html
    return []


def _detail_from_html(html: str, *, slug: str, local: str, company: str, url: str) -> dict:
    posted = extract_job_posting(html, page_url=url)
    h1 = _H1.search(html or "")
    title = posted.get("title") or strip_html(h1.group(1) if h1 else "") or "Untitled"
    chunk = html or ""
    for marker in ("Похожие вакансии", "same-vacancies", "похожие"):
        cut = chunk.casefold().find(marker.casefold())
        if cut > 0:
            chunk = chunk[:cut]
            break
    h1_m = _H1.search(chunk)
    if h1_m:
        chunk = chunk[h1_m.end() :]
    description = posted.get("description") or _job_text(chunk)[:12000]
    return {
        "id": career_id(slug, local),
        "title": title,
        "company": company,
        "description": description,
        "location": posted.get("location"),
        "work_format": posted.get("work_format"),
        "salary_raw": posted.get("salary_raw"),
        "source_url": url,
    }


def _grade_from_text(*parts: str) -> str | None:
    blob = " ".join(parts).lower()
    for grade in ("lead", "senior", "middle", "junior", "intern"):
        if grade in blob:
            return grade
    if "ведущ" in blob or "principal" in blob:
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


def _work_format(*parts: object) -> str | None:
    blob = " ".join(str(part) for part in parts if part).lower()
    if any(token in blob for token in ("удал", "remote", "дистанц")):
        return "удалённо"
    if any(token in blob for token in ("гибрид", "mixed", "гибк")):
        return "гибрид"
    if any(token in blob for token in ("офис", "office")):
        return "офис"
    return None


def normalize_career_job(detail: dict, listing_item: dict | None = None) -> dict:
    data = {**(listing_item or {}), **detail}
    raw_id = str(data.get("id") or data.get("source_id") or "")
    slug, local = split_career_id(raw_id)
    board = get_board(slug)
    company = data.get("company") or (board.name if board else None)
    url = data.get("source_url") or data.get("url") or ""
    skills = data.get("skills") or []
    if isinstance(skills, str):
        skills = [item.strip() for item in skills.split(",") if item.strip()]
    skills = [str(item).strip() for item in skills if str(item).strip()]
    description = strip_html(str(data.get("description") or data.get("short_summary") or ""))
    requirements = strip_html(str(data.get("requirements") or "")) or description
    salary_raw = data.get("salary_raw")
    salary_min, salary_max, currency = parse_salary(salary_raw if isinstance(salary_raw, str) else None)
    remote = bool(data.get("remote"))
    work_format = _work_format(data.get("work_format"), description) or ("удалённо" if remote else data.get("work_format"))
    if work_format == "удалённо":
        remote = True
    grade = data.get("grade") or _grade_from_text(str(data.get("title") or ""), description, " ".join(skills))
    tags: list[str] = ["career"]
    if slug:
        tags.append(slug)
    if grade:
        tags.append(grade)
    if remote:
        tags.append("удалённо")
    if data.get("specialty"):
        tags.append(str(data["specialty"]))
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
        "source": "career",
        "source_id": career_id(slug, local) if slug else raw_id,
        "source_url": url,
        "title": data.get("title") or "Untitled",
        "company": company,
        "company_icon": normalize_company_icon(board.logo_url if board else None)
        or normalize_company_icon(data.get("company_icon"), page_url=url or (board.origin if board else None)),
        "grade": grade,
        "work_format": work_format,
        "category": "development",
        "location": data.get("location"),
        "salary_raw": salary_raw if isinstance(salary_raw, str) else None,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency or "RUB",
        "description": description or None,
        "requirements": requirements or None,
        "skills": skills,
        "tags": unique[:24],
        "raw_payload": data,
        "published_at": data.get("published_at"),
    }


class CareerSource:
    name = "career"

    def __init__(self, http: PoliteHttp | None = None) -> None:
        self.http = http or PoliteHttp()
        self._yandex_cursor: str | None = None

    def _board(self, query_params: dict | None) -> CareerBoard:
        params = normalize_career_params(query_params)
        board = get_board(params["company"])
        if board is None:
            raise ValueError("Неизвестная компания")
        return board

    async def search(self, query_params: dict, *, page: int, limit: int = 20) -> dict:
        params = normalize_career_params(query_params)
        board = self._board(query_params)
        if board.kind == "aviasales":
            result = await self._search_aviasales(board, page, limit)
        elif board.kind == "vk":
            result = await self._search_vk(board, page, limit)
        elif board.kind == "yandex":
            result = await self._search_yandex(board, page, limit, params)
        elif board.kind == "avito":
            result = await self._search_avito(board, page)
        elif board.kind == "kaspersky":
            result = await self._search_kaspersky(board, page)
        elif board.kind == "tbank":
            result = await self._search_tbank(board, page)
        elif board.kind == "yadro":
            result = await self._search_yadro(board, page)
        elif board.kind == "megafon":
            result = await self._search_megafon(board, page)
        elif board.kind == "solar":
            result = await self._search_solar(board, page)
        elif board.kind == "selectel":
            result = await self._search_selectel(board, page)
        elif board.kind == "x5":
            result = await self._search_x5(board, page)
        elif board.kind == "itone":
            result = await self._search_itone(board, page)
        elif board.kind == "cloudru":
            result = await self._search_cloudru(board, page)
        elif board.kind == "croc":
            result = await self._search_croc(board, page)
        elif board.kind == "jet":
            result = await self._search_jet(board, page)
        elif board.kind == "mts":
            result = await self._search_mts(board, page)
        elif board.kind == "ibs":
            result = await self._search_ibs(board, page)
        elif board.kind == "2gis":
            result = await self._search_dgis(board, page)
        elif board.kind == "alfa":
            result = await self._search_alfa(board, page)
        elif board.kind == "kontur":
            result = await self._search_kontur(board, page)
        elif board.kind == "wb":
            result = await self._search_wb(board, page)
        elif board.kind == "ozon":
            result = await self._search_ozon(board, page)
        else:
            result = {"jobs": [], "has_more": False}
        jobs = [job for job in result.get("jobs") or [] if career_job_matches(job, params)]
        result["jobs"] = jobs
        result["total_count"] = len(jobs)
        return result

    async def detail(self, job_id: str | int, query_params: dict | None = None) -> dict:
        slug, local = split_career_id(job_id, normalize_career_params(query_params)["company"])
        board = get_board(slug) or self._board(query_params)
        if board.kind == "aviasales":
            html = await self.http.get_text(
                f"{board.origin}/about/vacancies/{local}",
                referer=board.listing_url,
            )
            return parse_aviasales_detail(html, career_id(board.slug, local))
        if board.kind == "vk":
            html = await self.http.get_text(
                f"{board.origin}/vacancy/{local}/",
                referer=board.listing_url,
            )
            return parse_vk_detail_html(html, career_id(board.slug, local))
        if board.kind == "yandex":
            data = await self.http.get_json(f"{YANDEX_API}{local}/", referer=board.listing_url)
            return parse_yandex_detail(data, career_id(board.slug, local))
        if board.kind == "avito":
            cat, _, num = local.partition("/")
            if not num:
                num = cat
                cat = "razrabotka"
            html = await self.http.get_text(
                f"{board.origin}/vacancies/{cat}/{num}/",
                referer=board.listing_url,
            )
            return parse_avito_detail(html, career_id(board.slug, f"{cat}/{num}"))
        if board.kind == "kaspersky":
            html = await self.http.get_text(f"{board.origin}/vacancy/{local}", referer=board.listing_url)
            return parse_kaspersky_detail(html, career_id(board.slug, local))
        if board.kind == "tbank":
            seo, _, uuid = local.partition("/")
            if not uuid:
                uuid = seo
                seo = uuid
            html = await self.http.get_text(
                f"{board.origin}/career/it/vacancy/moscow/{seo}/{uuid}/",
                referer=board.listing_url,
            )
            return parse_tbank_detail(html, career_id(board.slug, f"{seo}/{uuid}"))
        if board.kind == "yadro":
            payload = await self.http.get_json(YADRO_API, referer=board.listing_url)
            return parse_yadro_detail(payload, career_id(board.slug, local))
        if board.kind == "megafon":
            city_id, _, slug = local.partition("/")
            if not slug:
                slug = city_id
                city_id = "1"
            payload = await self.http.get_json(
                f"{MEGAFON_API}/{slug}",
                params={"cityId": city_id},
                referer=board.listing_url,
            )
            return parse_megafon_detail(payload, career_id(board.slug, f"{city_id}/{slug}"))
        if board.kind == "solar":
            html = await self.http.get_text(
                f"{board.origin}/vacancies/{local}/",
                referer=board.listing_url,
            )
            return parse_solar_detail(html, career_id(board.slug, local))
        if board.kind == "selectel":
            html = await self.http.get_text(
                f"{board.origin}/careers/all/vacancy/{local}/",
                referer=board.listing_url,
            )
            return parse_selectel_detail(html, career_id(board.slug, local))
        if board.kind == "x5":
            html = await self.http.get_text(f"{board.origin}/vacancy/{local}", referer=board.listing_url)
            return parse_x5_detail(html, career_id(board.slug, local))
        if board.kind == "itone":
            html = await self.http.get_text(
                f"{board.origin}/vacancies/{local}/",
                referer=board.listing_url,
            )
            return parse_itone_detail(html, career_id(board.slug, local))
        if board.kind == "cloudru":
            html = await self.http.get_text(
                f"{board.origin}/career/vacancies/{local}",
                referer=board.listing_url,
            )
            return parse_cloudru_detail(html, career_id(board.slug, local))
        if board.kind == "croc":
            html = await self.http.get_text(
                f"{board.origin}/vacancies/{local}/",
                referer=board.listing_url,
            )
            return parse_croc_detail(html, career_id(board.slug, local))
        if board.kind == "jet":
            html = await self.http.get_text(
                f"{board.origin}/career/vacancies/{local}/",
                referer=board.listing_url,
            )
            return parse_jet_detail(html, career_id(board.slug, local))
        if board.kind == "mts":
            payload = await self.http.get_json(f"{MTS_API}/{local}", referer=board.listing_url)
            return parse_mts_detail(payload if isinstance(payload, dict) else {}, career_id(board.slug, local))
        if board.kind == "ibs":
            html = await self.http.get_text(
                f"{board.origin}/career/jobs/{local}/",
                referer=board.listing_url,
            )
            return parse_ibs_detail(html, career_id(board.slug, local))
        if board.kind == "2gis":
            payload = await self.http.get_json(f"{TGIS_API}/{local}", referer=board.listing_url)
            return parse_dgis_detail(payload if isinstance(payload, dict) else {}, career_id(board.slug, local))
        if board.kind == "alfa":
            payload = await self.http.get_json(f"{ALFA_API}/{local}", referer=board.listing_url)
            return parse_alfa_detail(payload if isinstance(payload, dict) else {}, career_id(board.slug, local))
        if board.kind == "kontur":
            html = await self.http.get_text(
                f"{board.origin}/career/vacancies/{local}",
                referer=board.listing_url,
            )
            return parse_kontur_detail(html, career_id(board.slug, local))
        if board.kind == "wb":
            payload = await self.http.get_json(
                f"{WB_API}/{local}",
                referer=f"{board.origin}/",
            )
            return parse_wb_detail(payload if isinstance(payload, dict) else {}, career_id(board.slug, local))
        return {"id": career_id(board.slug, local)}

    def normalize(self, detail: dict, listing_item: dict | None = None) -> dict:
        return normalize_career_job(detail, listing_item)

    async def _search_aviasales(self, board: CareerBoard, page: int, _limit: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        html = await self.http.get_text(board.listing_url, referer=board.origin)
        jobs = parse_aviasales_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_vk(self, board: CareerBoard, page: int, limit: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        offset = 0
        while offset < 250 and len(jobs) < 250:
            payload = await self.http.get_json(
                VK_API,
                params={"limit": 25, "offset": offset},
                referer=board.listing_url,
            )
            chunk = parse_vk_listing(payload)
            jobs.extend(chunk)
            results = payload.get("results") if isinstance(payload, dict) else None
            if not results:
                break
            offset += 25
            if not payload.get("next"):
                break
        return {"jobs": jobs[: max(limit, 250)], "has_more": False, "total_count": len(jobs)}

    async def _search_yandex(self, board: CareerBoard, page: int, limit: int, params: dict | None = None) -> dict:
        if page == 1:
            self._yandex_cursor = None
        # Femida rejects large OR lists of professions (returns empty). A few
        # public_professions work; «все стеки» must omit the filter and rely on
        # local career_job_matches / stack lexicon instead.
        profs = list(yandex_professions(params or {}))
        params_q: list[tuple[str, str]] = [("page_size", str(min(20, max(1, limit))))]
        if 0 < len(profs) <= 4:
            for profession in profs:
                params_q.append(("public_professions", profession))
        if self._yandex_cursor:
            params_q.append(("cursor", self._yandex_cursor))
        payload = await self.http.get_json(YANDEX_API, params=params_q, referer=board.listing_url)
        jobs = parse_yandex_listing(payload)
        next_url = payload.get("next") if isinstance(payload, dict) else None
        cursor = None
        if isinstance(next_url, str) and next_url:
            cursor = (parse_qs(urlparse(next_url).query).get("cursor") or [None])[0]
        self._yandex_cursor = cursor
        return {
            "jobs": jobs,
            "has_more": bool(cursor),
            "total_count": payload.get("count") if isinstance(payload, dict) else len(jobs),
        }

    async def _search_avito(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        for slug in sorted(AVITO_IT_SLUGS):
            html = await self.http.get_text(f"{board.origin}/vacancies/{slug}/", referer=board.listing_url)
            for job in parse_avito_listing(html):
                key = str(job.get("id") or "")
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_kaspersky(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        for category_id in sorted(KASPERSKY_IT_CATEGORIES):
            html = await self.http.get_text(
                f"{board.origin}/vacancies",
                params={"category": str(category_id)},
                referer=board.listing_url,
            )
            for job in parse_kaspersky_listing(html, category_id=category_id):
                key = str(job.get("id") or "")
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_tbank(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs = await self._fetch_tbank_it(board)
        if not jobs:
            html = await self.http.get_text(board.listing_url, referer=board.origin)
            jobs = parse_tbank_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _fetch_tbank_it(self, board: CareerBoard) -> list[dict]:
        jobs: list[dict] = []
        seen: set[str] = set()
        offset = 0
        pages = 0
        while offset < TBANK_CAP and len(jobs) < TBANK_CAP and pages < 8:
            try:
                payload = await self.http.post_json(
                    TBANK_API,
                    json={
                        "filters": {},
                        "pagination": {"it": {"offset": offset, "isFinished": False}},
                        "limit": TBANK_PAGE,
                    },
                    referer=board.listing_url,
                )
            except Exception:
                break
            pages += 1
            chunk = parse_tbank_api_payload(payload if isinstance(payload, dict) else {})
            fresh = 0
            for job in chunk:
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                fresh += 1
            nxt = tbank_next_offset(payload if isinstance(payload, dict) else {}, offset)
            if nxt is None or fresh == 0:
                break
            offset = nxt
        return jobs

    async def _search_yadro(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        payload = await self.http.get_json(YADRO_API, referer=board.listing_url)
        jobs = parse_yadro_listing(payload)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_megafon(self, board: CareerBoard, page: int) -> dict:
        payload = await self.http.get_json(
            MEGAFON_API,
            params=[
                ("page", str(max(1, page))),
                ("specialties", ",".join(str(item) for item in MEGAFON_IT_SPECIALTIES)),
            ],
            referer=board.listing_url,
        )
        jobs = parse_megafon_listing(payload if isinstance(payload, dict) else {})
        pages = 0
        if isinstance(payload, dict):
            try:
                pages = int(payload.get("pages") or 0)
            except (TypeError, ValueError):
                pages = 0
        return {"jobs": jobs, "has_more": page < pages, "total_count": payload.get("total") if isinstance(payload, dict) else len(jobs)}

    async def _search_solar(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        html = await self.http.get_text(board.listing_url, referer=board.origin)
        jobs = parse_solar_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_selectel(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        html = await self.http.get_text(board.listing_url, referer=board.origin)
        jobs = parse_selectel_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_x5(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        for index in range(1, X5_PAGES + 1):
            url = board.listing_url if index == 1 else f"{board.listing_url}?page={index}"
            html = await self.http.get_text(url, referer=board.listing_url)
            fresh = 0
            for job in parse_x5_listing(html):
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                fresh += 1
            if fresh == 0:
                break
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_itone(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        skip = 0
        while skip < ITONE_CAP and len(jobs) < ITONE_CAP:
            payload = await self.http.get_json(
                ITONE_API,
                params={"skip": str(skip), "take": str(ITONE_TAKE)},
                referer=board.listing_url,
            )
            chunk = parse_itone_listing(payload)
            fresh = 0
            for job in chunk:
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                fresh += 1
            if fresh == 0 or len(chunk) < ITONE_TAKE:
                break
            skip += ITONE_TAKE
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_cloudru(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        html = await self.http.get_text(board.listing_url, referer=board.origin)
        jobs = parse_cloudru_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_croc(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        for section_id in sorted(CROC_IT_SECTIONS):
            html = await self.http.get_text(
                f"{board.origin}/vacancies/",
                params={"sections": str(section_id)},
                referer=board.listing_url,
            )
            for job in parse_croc_listing(html):
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_jet(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        for index in range(1, JET_PAGES + 1):
            url = board.listing_url if index == 1 else f"{board.listing_url}?page={index}"
            html = await self.http.get_text(url, referer=board.listing_url)
            fresh = 0
            for job in parse_jet_listing(html):
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                fresh += 1
            if fresh == 0:
                break
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_mts(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        api_page = 1
        while len(jobs) < MTS_CAP and api_page <= 12:
            payload = await self.http.get_json(
                MTS_API,
                params=[("pagination[page]", str(api_page)), ("pagination[pageSize]", str(MTS_PAGE))],
                referer=board.listing_url,
            )
            chunk = parse_mts_listing(payload if isinstance(payload, dict) else {})
            if not chunk:
                break
            fresh = 0
            for job in chunk:
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                fresh += 1
            meta = payload.get("meta") if isinstance(payload, dict) else {}
            pagination = meta.get("pagination") if isinstance(meta, dict) else {}
            page_count = pagination.get("pageCount") if isinstance(pagination, dict) else None
            if fresh == 0 or (page_count is not None and api_page >= int(page_count)):
                break
            api_page += 1
        return {"jobs": jobs[:MTS_CAP], "has_more": False, "total_count": len(jobs)}

    async def _search_ibs(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        for slug in IBS_IT_FILTERS:
            html = await self.http.get_text(
                f"{board.origin}/career/jobs/filter/{slug}/apply/",
                referer=board.listing_url,
            )
            for job in parse_ibs_listing(html):
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_dgis(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        api_page = 1
        while len(jobs) < TGIS_CAP and api_page <= 12:
            params: list[tuple[str, str | int]] = [
                ("pageSize", TGIS_PAGE),
                ("page", api_page),
            ]
            for direction_id in TGIS_IT_DIRECTIONS:
                params.append(("direction[]", direction_id))
            payload = await self.http.get_json(TGIS_API, params=params, referer=board.listing_url)
            chunk = parse_dgis_listing(payload if isinstance(payload, dict) else {})
            if not chunk:
                break
            fresh = 0
            for job in chunk:
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                fresh += 1
            total_pages = payload.get("totalPages") if isinstance(payload, dict) else None
            if fresh == 0 or (total_pages is not None and api_page >= int(total_pages)):
                break
            api_page += 1
        return {"jobs": jobs[:TGIS_CAP], "has_more": False, "total_count": len(jobs)}

    async def _search_alfa(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        skip = 0
        total = None
        while len(jobs) < ALFA_CAP and skip <= 4000:
            payload = await self.http.get_json(
                ALFA_API,
                params={"take": ALFA_PAGE, "skip": skip},
                referer=board.listing_url,
            )
            if total is None and isinstance(payload, dict):
                total = int(payload.get("total") or 0)
            chunk = parse_alfa_listing(payload if isinstance(payload, dict) else {})
            if not chunk and skip >= (total or 0):
                break
            for job in chunk:
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
            skip += ALFA_PAGE
            if total is not None and skip >= total:
                break
            if not (payload.get("items") if isinstance(payload, dict) else None):
                break
        return {"jobs": jobs[:ALFA_CAP], "has_more": False, "total_count": len(jobs)}

    async def _search_kontur(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        html = await self.http.get_text(board.listing_url, referer=board.origin)
        jobs = parse_kontur_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}

    async def _search_wb(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        jobs: list[dict] = []
        seen: set[str] = set()
        offset = 0
        while len(jobs) < WB_CAP and offset <= 2000:
            params: list[tuple[str, str | int]] = [("limit", WB_PAGE), ("offset", offset)]
            for direction_id in WB_IT_DIRECTIONS:
                params.append(("direction_ids[]", direction_id))
            payload = await self.http.get_json(WB_API, params=params, referer=f"{board.origin}/")
            chunk = parse_wb_listing(payload if isinstance(payload, dict) else {})
            if not chunk:
                break
            for job in chunk:
                key = str(job.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
            offset += WB_PAGE
            data = payload.get("data") if isinstance(payload, dict) else {}
            total = None
            if isinstance(data, dict):
                range_meta = data.get("range")
                if isinstance(range_meta, dict):
                    total = range_meta.get("count")
            if total is not None and offset >= int(total):
                break
        return {"jobs": jobs[:WB_CAP], "has_more": False, "total_count": len(jobs)}

    async def _search_ozon(self, board: CareerBoard, page: int) -> dict:
        if page > 1:
            return {"jobs": [], "has_more": False}
        try:
            html = await self.http.get_text(board.listing_url, referer=board.origin)
        except Exception:
            return {"jobs": [], "has_more": False}
        jobs = parse_ozon_listing(html)
        return {"jobs": jobs, "has_more": False, "total_count": len(jobs)}
