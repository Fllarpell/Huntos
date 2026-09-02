from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import Vacancy
from app.services.vacancy_write import company_key, is_anon_company_name, normalize_inn

HIREHI_ORIGIN = "https://hirehi.ru"

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


async def lookup_cached_icon(session: AsyncSession, vacancy: Vacancy) -> str | None:
    user_id = vacancy.user_id
    if user_id is None:
        return None
    inn = normalize_inn(vacancy.company_inn)
    if inn:
        rows = (
            await session.execute(
                select(Vacancy.company_icon).where(
                    Vacancy.user_id == user_id,
                    Vacancy.company_inn == inn,
                    Vacancy.company_icon.isnot(None),
                    Vacancy.id != vacancy.id,
                )
            )
        ).scalars()
        for raw in rows:
            found = normalize_company_icon(raw)
            if found:
                return found
    if is_anon_company_name(vacancy.company):
        return None
    key = company_key(vacancy.company)
    if not key:
        return None
    rows = (
        await session.execute(
            select(Vacancy.company_icon).where(
                Vacancy.user_id == user_id,
                func.lower(func.trim(Vacancy.company)) == key,
                Vacancy.company_icon.isnot(None),
                Vacancy.id != vacancy.id,
            )
        )
    ).scalars()
    for raw in rows:
        found = normalize_company_icon(raw)
        if found:
            return found
    return None


async def _share_icon(session: AsyncSession, vacancy: Vacancy, icon: str) -> None:
    user_id = vacancy.user_id
    if user_id is None:
        return
    inn = normalize_inn(vacancy.company_inn)
    stmt = select(Vacancy).where(Vacancy.user_id == user_id, Vacancy.id != vacancy.id)
    if inn:
        stmt = stmt.where(Vacancy.company_inn == inn)
    else:
        if is_anon_company_name(vacancy.company):
            return
        key = company_key(vacancy.company)
        if not key:
            return
        stmt = stmt.where(func.lower(func.trim(Vacancy.company)) == key)
    siblings = (await session.execute(stmt)).scalars().all()
    for sibling in siblings:
        if normalize_company_icon(sibling.company_icon):
            continue
        sibling.company_icon = icon


async def hydrate_company_icon(session: AsyncSession, vacancy: Vacancy) -> None:
    own = normalize_company_icon(vacancy.company_icon, page_url=vacancy.source_url)
    vacancy.company_icon = own
    if own:
        await _share_icon(session, vacancy, own)
        return
    cached = await lookup_cached_icon(session, vacancy)
    if cached:
        vacancy.company_icon = cached


async def backfill_company_icons(session: AsyncSession) -> int:
    rows = (await session.execute(select(Vacancy))).scalars().all()
    changed = 0
    by_inn: dict[tuple[int, str], str] = {}
    by_name: dict[tuple[int, str], str] = {}
    for vacancy in rows:
        cleaned = normalize_company_icon(vacancy.company_icon, page_url=vacancy.source_url)
        if cleaned != vacancy.company_icon:
            vacancy.company_icon = cleaned
            changed += 1
        if not cleaned or vacancy.user_id is None:
            continue
        inn = normalize_inn(vacancy.company_inn)
        if inn:
            by_inn.setdefault((vacancy.user_id, inn), cleaned)
        if not is_anon_company_name(vacancy.company):
            key = company_key(vacancy.company)
            if key:
                by_name.setdefault((vacancy.user_id, key), cleaned)
    for vacancy in rows:
        if vacancy.user_id is None or normalize_company_icon(vacancy.company_icon):
            continue
        picked = None
        inn = normalize_inn(vacancy.company_inn)
        if inn:
            picked = by_inn.get((vacancy.user_id, inn))
        if not picked and not is_anon_company_name(vacancy.company):
            key = company_key(vacancy.company)
            if key:
                picked = by_name.get((vacancy.user_id, key))
        if picked:
            vacancy.company_icon = picked
            changed += 1
    if changed:
        await session.commit()
    return changed
