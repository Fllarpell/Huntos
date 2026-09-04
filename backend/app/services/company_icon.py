from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import parse_qs, urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import Vacancy
from app.services.vacancy_write import is_anon_company_name, normalize_inn

HIREHI_ORIGIN = "https://hirehi.ru"
GETMATCH_ORIGIN = "https://getmatch.ru"
_GOOGLE_FAVICON = "https://www.google.com/s2/favicons?sz=128&domain="

_PRIVATE_HOST = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)")
_PLACEHOLDER_MARK = re.compile(
    r"hirehi-company-placeholder|hirehicompanyplaceholder",
    re.I,
)
_DATA_SVG = re.compile(r"^data:image/svg", re.I)
_DATA_RASTER = re.compile(r"^data:image/(png|jpe?g|webp|gif|avif)\b", re.I)
_TRACKING_PIXEL = re.compile(r"(?:/spacer\.|/blank\.gif|1x1\.(?:gif|png|webp))", re.I)


def _blocked_host(host: str) -> bool:
    name = host.lower().rstrip(".")
    if not name or name in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return True
    if name.endswith(".local") or name.endswith(".internal"):
        return True
    return bool(_PRIVATE_HOST.match(name))


def _is_placeholder(raw: str) -> bool:
    if _PLACEHOLDER_MARK.search(raw):
        return True
    if _DATA_SVG.match(raw):
        return True
    return bool(_TRACKING_PIXEL.search(raw))


def normalize_company_icon(raw: str | None, *, page_url: str | None = None) -> str | None:
    """Keep a logo only when a source actually handed us a fetchable picture.

    Drops HireHi letter-crest SVGs, generated data:svg, localhost, and empty.
    Relative `/static/uploads/...` from HireHi becomes an absolute URL.
    """
    text = (raw or "").strip()
    if not text or _is_placeholder(text):
        return None
    if _DATA_RASTER.match(text):
        return text[:4096]
    if text.startswith("//"):
        text = "https:" + text
    elif text.startswith("/"):
        if text.startswith("/static/"):
            text = urljoin(HIREHI_ORIGIN, text)
        elif page_url and page_url.startswith("http"):
            text = urljoin(page_url, text)
        else:
            return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.hostname or ""
    if _blocked_host(host):
        return None
    if not parsed.path or parsed.path == "/":
        return None
    return text[:1024]


def icon_for_career_vacancy(source: str | None, source_id: str | None) -> str | None:
    if source != "career":
        return None
    from app.services.scraper.sources.career_catalog import get_board

    slug = str(source_id or "").split(":", 1)[0]
    board = get_board(slug)
    return normalize_company_icon(board.logo_url if board else None)


_LEGAL_HEAD = re.compile(r"^(ооо|оао|зао|пао|ао|llc|ltd|inc|gmbh|npo|ao|zao|pao|ooo)")
_LEGAL_TAIL = re.compile(r"(ооо|оао|зао|пао|ао|llc|ltd|inc|gmbh|npo|ao|zao|pao|ooo)$")
_INDEX_KEY = "hunt_icon_index"

# Short RU/EN names that should share one logo in the inbox.
_BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "vk": ("vk", "вк", "вконтакте", "vk.com", "vkontakte"),
    "sber": ("sber", "сбер", "сбербанк", "sberbank", "сбертех", "sbertech"),
    "tbank": ("tbank", "t-bank", "тбанк", "т-банк", "tinkoff", "тинькофф"),
    "ozon": ("ozon", "озон"),
    "zvuk": ("zvuk", "звук", "sberzvuk", "сберзвук"),
    "yandex": (
        "yandex",
        "яндекс",
        "ya.ru",
        "ytsaurus",
        "кинопоиск",
        "kinopoisk",
        "фантех",
        "fantech",
        "яндекс маркет",
        "yandex market",
    ),
    "aviasales": ("aviasales", "авиасейлс"),
    "avito": ("avito", "авито"),
    "kaspersky": ("kaspersky", "касперск", "лаборатория касперского"),
    "wb": ("wildberries", "вайлдберриз", "wildberries.ru"),
    "alfa": ("alfabank", "альфа-банк", "альфабанк", "alfa-bank"),
    "mts": ("mts", "мтс"),
    "2gis": ("2gis", "2гис", "дгис", "twogis"),
    "ostrovok": ("ostrovok", "островок"),
    "luxoft": ("luxoft", "люксофт"),
}

_BRAND_DOMAINS: dict[str, str] = {
    "vk": "vk.com",
    "sber": "sber.ru",
    "tbank": "tbank.ru",
    "ozon": "ozon.ru",
    "zvuk": "zvuk.com",
    "yandex": "yandex.ru",
    "aviasales": "aviasales.ru",
    "avito": "avito.ru",
    "kaspersky": "kaspersky.ru",
    "wb": "wildberries.ru",
    "alfa": "alfabank.ru",
    "mts": "mts.ru",
    "2gis": "2gis.ru",
    "ostrovok": "ostrovok.ru",
    "luxoft": "luxoft.com",
}

_JOB_HOSTS = frozenset(
    {
        "hh.ru",
        "www.hh.ru",
        "hirehi.ru",
        "www.hirehi.ru",
        "getmatch.ru",
        "www.getmatch.ru",
        "career.habr.com",
        "habr.com",
        "t.me",
        "telegram.me",
        "web.telegram.org",
    }
)
_GETMATCH_FILE = re.compile(r"^[\w.-]+\.(png|jpe?g|webp|gif|svg)(?:\?.*)?$", re.I)
_LATIN_DOMAIN = re.compile(r"\b(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z]{2,24})+)\b", re.I)
_LATIN_TOKEN = re.compile(r"[a-z][a-z0-9]{3,}", re.I)


def _compact_name(name: str) -> str:
    text = (name or "").lower().replace("ё", "е")
    compact = re.sub(r"[^a-zа-я0-9]+", "", text)
    compact = _LEGAL_HEAD.sub("", compact)
    return _LEGAL_TAIL.sub("", compact)


def icon_brand_key(name: str | None) -> str | None:
    """Identity for sharing logos: VK == ВК == ВКонтакте, not NDA."""
    if is_anon_company_name(name):
        return None
    raw = (name or "").strip().lower().replace("ё", "е")
    if not raw:
        return None
    compact = _compact_name(raw)
    for brand, aliases in _BRAND_ALIASES.items():
        for alias in aliases:
            alias_c = _compact_name(alias)
            if compact and compact == alias_c:
                return brand
            if compact and len(alias_c) >= 4 and compact.startswith(alias_c):
                return brand
            if compact and len(alias_c) >= 5 and alias_c in compact:
                return brand
            if raw == alias or raw.startswith(f"{alias} ") or raw.startswith(f"{alias}/") or raw.startswith(f"{alias},"):
                return brand
    return compact or None


def expand_brand_names(name: str) -> list[str]:
    """User-facing name plus RU/EN aliases so 'яндекс' also covers 'Yandex'."""
    raw = (name or "").strip()
    if not raw:
        return []
    found = [raw]
    brand = icon_brand_key(raw)
    if brand and brand in _BRAND_ALIASES:
        found.extend(_BRAND_ALIASES[brand])
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        key = item.casefold().replace("ё", "е")
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def resolve_getmatch_logotype(raw: str | None) -> str | None:
    """GetMatch stores `company.logotype` as a filename, not a URL."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("/"):
        return urljoin(GETMATCH_ORIGIN, text)
    if text.startswith("uploads/"):
        return f"{GETMATCH_ORIGIN}/{text}"
    if _GETMATCH_FILE.match(text):
        return f"{GETMATCH_ORIGIN}/uploads/companies_logos/{text}"
    return None


def google_favicon(domain: str) -> str:
    host = domain.strip().lower().removeprefix("www.")
    return f"{_GOOGLE_FAVICON}{host}"


def infer_company_domain(name: str | None, source_url: str | None = None) -> str | None:
    if is_anon_company_name(name):
        return None
    brand = icon_brand_key(name)
    if brand and brand in _BRAND_DOMAINS:
        return _BRAND_DOMAINS[brand]
    text = (name or "").strip().lower().replace("ё", "е")
    found = _LATIN_DOMAIN.search(text)
    if found:
        return found.group(1).removeprefix("www.")
    host = (urlparse(source_url or "").hostname or "").lower()
    if host and host not in _JOB_HOSTS and not any(host.endswith(f".{item}") for item in _JOB_HOSTS):
        return host.removeprefix("www.")
    token = _LATIN_TOKEN.search((name or "").strip())
    if token:
        return f"{token.group(0).lower()}.com"
    return None


def fallback_company_icon(name: str | None, source_url: str | None = None) -> str | None:
    domain = infer_company_domain(name, source_url)
    if not domain:
        return None
    return normalize_company_icon(google_favicon(domain))


def icon_from_raw_payload(source: str | None, raw: object, page_url: str | None = None) -> str | None:
    if source != "getmatch" or not isinstance(raw, dict):
        return None
    company = raw.get("company")
    filename = None
    if isinstance(company, dict):
        filename = company.get("logotype") or company.get("logo")
    return normalize_company_icon(
        resolve_getmatch_logotype(str(filename) if filename else None),
        page_url=page_url or GETMATCH_ORIGIN,
    )


def owned_icons(vacancy: Vacancy) -> list[str]:
    page = vacancy.source_url
    found = [
        normalize_company_icon(vacancy.company_icon, page_url=page),
        icon_for_career_vacancy(vacancy.source, vacancy.source_id),
        icon_from_raw_payload(vacancy.source, vacancy.raw_payload, page),
    ]
    return [item for item in found if item]


def icon_identity(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").rstrip("/").lower()
    if "google.com" in host and "favicon" in path:
        domain = (parse_qs(parsed.query).get("domain") or [""])[0].lower()
        return f"favicon:{domain}" if domain else f"{host}{path}"
    return f"{host}{path}"


def _icon_quality(url: str) -> int:
    host = (urlparse(url).hostname or "").lower()
    path = (urlparse(url).path or "").lower()
    if "gstatic.com" in host or ("google.com" in host and "favicon" in path):
        return 0
    if "hhcdn" in host or host.endswith("hh.ru"):
        return 3
    if "hirehi.ru" in host and "/static/uploads/" in path:
        return 3
    if "getmatch.ru" in host and "/uploads/" in path:
        return 2
    if "geekjob.ru" in host and "/storage/company/" in path:
        return 2
    if host.endswith("vk.com") or "vkcdn" in host:
        return 2
    return 1


def pick_consensus_icon(urls: list[str]) -> tuple[str | None, int, int]:
    """Most frequent logo wins. Returns (url, winner_count, runner_up_count)."""
    cleaned = [item for item in (normalize_company_icon(url) for url in urls) if item]
    if not cleaned:
        return None, 0, 0
    groups: dict[str, list[str]] = defaultdict(list)
    for url in cleaned:
        groups[icon_identity(url)].append(url)
    ranked = sorted(
        groups.items(),
        key=lambda item: (-len(item[1]), -_icon_quality(item[1][0]), item[0]),
    )
    winner_urls = ranked[0][1]
    runner = len(ranked[1][1]) if len(ranked) > 1 else 0
    best = max(winner_urls, key=_icon_quality)
    return best, len(winner_urls), runner


def consensus_should_overwrite(current: str | None, winner: str, win_count: int, runner_count: int) -> bool:
    own = normalize_company_icon(current)
    if not own:
        return True
    if icon_identity(own) == icon_identity(winner):
        return False
    if win_count >= 2 and win_count > runner_count:
        return True
    if _icon_quality(winner) > _icon_quality(own) and win_count >= runner_count:
        return True
    return False


def _image_url(node: object) -> str | None:
    if isinstance(node, str):
        return node.strip() or None
    if isinstance(node, list):
        for item in node:
            found = _image_url(item)
            if found:
                return found
        return None
    if isinstance(node, dict):
        for key in ("url", "contentUrl", "src"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return _image_url(node.get("logo") or node.get("image"))
    return None


def logo_from_hiring_org(org: object, *, page_url: str | None = None) -> str | None:
    """Schema.org hiringOrganization.logo / image — not JobPosting.image or og:image."""
    if isinstance(org, str):
        return None
    if not isinstance(org, dict):
        return None
    for key in ("logo", "image"):
        found = normalize_company_icon(_image_url(org.get(key)), page_url=page_url)
        if found:
            return found
    return None


async def _icon_index(session: AsyncSession) -> dict[str, dict[str, list[str]]]:
    cached = session.info.get(_INDEX_KEY)
    if cached is not None:
        return cached
    rows = (await session.execute(select(Vacancy))).scalars().all()
    by_brand: dict[str, list[str]] = defaultdict(list)
    by_inn: dict[str, list[str]] = defaultdict(list)
    for vacancy in rows:
        urls = owned_icons(vacancy)
        if not urls:
            continue
        inn_n = normalize_inn(vacancy.company_inn)
        brand = icon_brand_key(vacancy.company)
        for url in urls:
            if inn_n:
                by_inn[inn_n].append(url)
            if brand:
                by_brand[brand].append(url)
    index = {"brand": dict(by_brand), "inn": dict(by_inn)}
    session.info[_INDEX_KEY] = index
    return index


def _drop_icon_index(session: AsyncSession) -> None:
    session.info.pop(_INDEX_KEY, None)


async def lookup_cached_icon(session: AsyncSession, vacancy: Vacancy) -> str | None:
    index = await _icon_index(session)
    inn = normalize_inn(vacancy.company_inn)
    urls: list[str] = []
    if inn:
        urls.extend(index["inn"].get(inn) or [])
    brand = icon_brand_key(vacancy.company)
    if brand:
        urls.extend(index["brand"].get(brand) or [])
    winner, _win, _runner = pick_consensus_icon(urls)
    return winner


async def _share_icon(session: AsyncSession, vacancy: Vacancy, icon: str, *, win_count: int = 1, runner_count: int = 0) -> None:
    user_id = vacancy.user_id
    brand = icon_brand_key(vacancy.company)
    inn = normalize_inn(vacancy.company_inn)
    if not brand and not inn:
        return
    stmt = select(Vacancy).where(Vacancy.id != vacancy.id)
    if user_id is not None:
        stmt = stmt.where(Vacancy.user_id == user_id)
    siblings = (await session.execute(stmt)).scalars().all()
    changed = False
    for sibling in siblings:
        same_inn = inn and normalize_inn(sibling.company_inn) == inn
        same_brand = brand and icon_brand_key(sibling.company) == brand
        if not same_inn and not same_brand:
            continue
        if is_anon_company_name(sibling.company) and not same_inn:
            continue
        if consensus_should_overwrite(sibling.company_icon, icon, win_count, runner_count):
            sibling.company_icon = icon
            changed = True
    if changed:
        _drop_icon_index(session)


async def hydrate_company_icon(session: AsyncSession, vacancy: Vacancy) -> None:
    own_urls = owned_icons(vacancy)
    own = own_urls[0] if own_urls else None
    index = await _icon_index(session)
    pile: list[str] = []
    inn = normalize_inn(vacancy.company_inn)
    if inn:
        pile.extend(index["inn"].get(inn) or [])
    brand = icon_brand_key(vacancy.company)
    if brand:
        pile.extend(index["brand"].get(brand) or [])
    pile.extend(own_urls)
    winner, win_count, runner_count = pick_consensus_icon(pile)
    if not winner:
        winner = fallback_company_icon(vacancy.company, vacancy.source_url)
        win_count, runner_count = (1, 0) if winner else (0, 0)
    if not winner:
        vacancy.company_icon = own
        return
    if consensus_should_overwrite(own, winner, win_count, runner_count):
        vacancy.company_icon = winner
    else:
        vacancy.company_icon = own or winner
    await _share_icon(session, vacancy, vacancy.company_icon, win_count=win_count, runner_count=runner_count)


async def backfill_company_icons(session: AsyncSession) -> int:
    rows = (await session.execute(select(Vacancy))).scalars().all()
    by_inn: dict[str, list[str]] = defaultdict(list)
    by_brand: dict[str, list[str]] = defaultdict(list)
    for vacancy in rows:
        for url in owned_icons(vacancy):
            inn = normalize_inn(vacancy.company_inn)
            if inn:
                by_inn[inn].append(url)
            brand = icon_brand_key(vacancy.company)
            if brand:
                by_brand[brand].append(url)
            if vacancy.source == "career":
                slug = str(vacancy.source_id or "").split(":", 1)[0]
                if slug and slug != brand:
                    by_brand[slug].append(url)
    changed = 0
    for vacancy in rows:
        own_urls = owned_icons(vacancy)
        own = own_urls[0] if own_urls else None
        pile: list[str] = []
        inn = normalize_inn(vacancy.company_inn)
        if inn:
            pile.extend(by_inn.get(inn) or [])
        brand = icon_brand_key(vacancy.company)
        if brand:
            pile.extend(by_brand.get(brand) or [])
        if vacancy.source == "career":
            slug = str(vacancy.source_id or "").split(":", 1)[0]
            if slug:
                pile.extend(by_brand.get(slug) or [])
        pile.extend(own_urls)
        winner, win_count, runner_count = pick_consensus_icon(pile)
        if not winner:
            winner = fallback_company_icon(vacancy.company, vacancy.source_url)
        if not winner:
            next_icon = own
        elif consensus_should_overwrite(own, winner, win_count, runner_count):
            next_icon = winner
        else:
            next_icon = own or winner
        if next_icon != vacancy.company_icon:
            vacancy.company_icon = next_icon
            changed += 1
    if changed:
        await session.commit()
        _drop_icon_index(session)
    return changed
