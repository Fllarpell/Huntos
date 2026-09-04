from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import String, cast
from sqlalchemy.sql import ColumnElement

from app.models.vacancy import Vacancy
from app.services.company_icon import _BRAND_ALIASES, _BRAND_DOMAINS, _compact_name, expand_brand_names, icon_brand_key
from app.services.search_text import fold_expr

_MAX_NAMES = 32
_MAX_LEN = 80
_SHORT = 4

_HOST_EXTRAS: dict[str, tuple[str, ...]] = {
    "yandex": ("yandex.ru", "ya.ru", "yandex.com"),
    "vk": ("vk.company", "vk.com", "vkontakte.ru"),
    "sber": ("sber.ru", "sberbank.ru", "sbertech.ru"),
    "tbank": ("tbank.ru", "tinkoff.ru"),
    "ozon": ("ozon.ru", "ozon.tech"),
    "avito": ("avito.ru", "avito.com"),
    "aviasales": ("aviasales.ru",),
    "kaspersky": ("kaspersky.ru", "kaspersky.com"),
    "wb": ("wildberries.ru", "wb.ru", "rwb.ru"),
    "alfa": ("alfabank.ru", "alfabank.com"),
    "mts": ("mts.ru", "job.mts.ru"),
    "2gis": ("2gis.ru", "2gis.com"),
    "ostrovok": ("ostrovok.ru",),
    "luxoft": ("luxoft.com",),
    "zvuk": ("zvuk.com",),
}


def normalize_exclude_companies(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [bit.strip() for bit in raw.replace(";", ",").replace("\n", ",").split(",")]
    elif isinstance(raw, (list, tuple, set)):
        parts = [str(item).strip() for item in raw]
    else:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for name in parts:
        clipped = name[:_MAX_LEN].strip()
        if len(clipped) < 2:
            continue
        key = clipped.casefold().replace("ё", "е")
        if key in seen:
            continue
        seen.add(key)
        out.append(clipped)
        if len(out) >= _MAX_NAMES:
            break
    return out


def _needles_for(name: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in expand_brand_names(name):
        folded = item.casefold().replace("ё", "е")
        compact = _compact_name(item)
        for token in (folded, compact):
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


def _brands_for_name(name: str) -> set[str]:
    found: set[str] = set()
    brand = icon_brand_key(name)
    if brand in _BRAND_ALIASES:
        found.add(brand)
    slug = (name or "").strip().lower().replace("ё", "е")
    if slug in _BRAND_ALIASES:
        found.add(slug)
    from app.services.scraper.sources.career_catalog import get_board

    board = get_board(slug)
    if board:
        found.add(board.slug)
        mapped = icon_brand_key(board.name)
        if mapped in _BRAND_ALIASES:
            found.add(mapped)
    return found


def _host_needles(brand: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for host in (_BRAND_DOMAINS.get(brand), *(_HOST_EXTRAS.get(brand) or ())):
        text = (host or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    from app.services.scraper.sources.career_catalog import get_board

    board = get_board(brand)
    if board:
        for raw in (board.origin, board.listing_url):
            host = (urlparse(raw).hostname or "").lower()
            if host and host not in seen:
                seen.add(host)
                out.append(host)
    return out


def _career_slug(source: str | None, source_id: str | None) -> str | None:
    if (source or "").strip().lower() != "career":
        return None
    slug = str(source_id or "").split(":", 1)[0].strip().lower()
    return slug or None


def _text_hits_needle(needle: str, folded: str, compact: str) -> bool:
    if not needle:
        return False
    if len(needle) < _SHORT:
        return compact == needle or folded == needle or folded.startswith(f"{needle} ") or folded.startswith(f"{needle}.")
    return needle in folded or (bool(compact) and needle in compact)


def _blob(*parts: object) -> tuple[str, str]:
    text = " ".join(str(part) for part in parts if part)
    folded = text.casefold().replace("ё", "е")
    return folded, _compact_name(text)


def vacancy_is_excluded(
    names: object,
    *,
    company: str | None = None,
    title: str | None = None,
    source: str | None = None,
    source_id: str | None = None,
    source_url: str | None = None,
    company_icon: str | None = None,
    tags: object = None,
) -> bool:
    wanted = normalize_exclude_companies(names)
    if not wanted:
        return False
    folded, compact = _blob(company, title)
    url = f"{source_url or ''} {company_icon or ''}".casefold()
    tag_bits: list[str] = []
    if isinstance(tags, (list, tuple, set)):
        tag_bits = [str(item).strip().lower() for item in tags if str(item).strip()]
    slug = _career_slug(source, source_id)
    source_id_l = str(source_id or "").strip().lower()
    for name in wanted:
        brands = _brands_for_name(name)
        if slug and (slug in brands or icon_brand_key(slug) in brands):
            return True
        for brand in brands:
            if source_id_l.startswith(f"{brand}:"):
                return True
            if brand in tag_bits:
                return True
            for host in _host_needles(brand):
                if host in url:
                    return True
        other_brand = icon_brand_key(company)
        if other_brand and other_brand in brands:
            return True
        for needle in _needles_for(name):
            if _text_hits_needle(needle, folded, compact):
                return True
            if len(needle) >= _SHORT and needle in url:
                return True
    return False


def company_is_excluded(company: str | None, names: object) -> bool:
    return vacancy_is_excluded(names, company=company)


def vacancy_row_is_excluded(vacancy: Vacancy, names: object) -> bool:
    return vacancy_is_excluded(
        names,
        company=vacancy.company,
        title=vacancy.title,
        source=vacancy.source,
        source_id=vacancy.source_id,
        source_url=vacancy.source_url,
        company_icon=vacancy.company_icon,
        tags=vacancy.tags,
    )


def company_not_excluded_clause(names: object) -> ColumnElement | None:
    """Hide the whole brand: legal name, job title, career slug, logo host."""
    wanted = normalize_exclude_companies(names)
    if not wanted:
        return None
    company = fold_expr(Vacancy.company)
    title = fold_expr(Vacancy.title)
    url = fold_expr(Vacancy.source_url)
    icon = fold_expr(Vacancy.company_icon)
    source_id = fold_expr(Vacancy.source_id)
    tags_text = fold_expr(cast(Vacancy.tags, String))
    likes: list[ColumnElement] = []
    seen: set[str] = set()

    def add(expr: ColumnElement, key: str) -> None:
        if key in seen:
            return
        seen.add(key)
        likes.append(expr)

    for name in wanted:
        for needle in _needles_for(name):
            if len(needle) < _SHORT:
                add(company == needle, f"eq-c:{needle}")
                add(title == needle, f"eq-t:{needle}")
                add(company.like(f"{needle} %"), f"pre-c:{needle}")
                add(company.like(f"{needle}.%"), f"dot-c:{needle}")
                add(title.like(f"{needle} %"), f"pre-t:{needle}")
                continue
            add(company.like(f"%{needle}%"), f"c:{needle}")
            add(title.like(f"%{needle}%"), f"t:{needle}")
            add(url.like(f"%{needle}%"), f"u:{needle}")
            add(icon.like(f"%{needle}%"), f"i:{needle}")
        for brand in _brands_for_name(name):
            add(source_id.like(f"{brand}:%"), f"id:{brand}")
            add(tags_text.like(f'%"{brand}"%'), f"tag:{brand}")
            for host in _host_needles(brand):
                add(url.like(f"%{host}%"), f"host:{host}")
                add(icon.like(f"%{host}%"), f"icon:{host}")

    if not likes:
        return None
    hit = likes[0]
    for extra in likes[1:]:
        hit = hit | extra
    return ~hit
