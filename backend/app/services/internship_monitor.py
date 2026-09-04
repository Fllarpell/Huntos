from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internship_catalog import PROGRAMS, InternshipProgram
from app.services.scraper.http import PoliteHttp
from app.models.internship_monitor import InternshipMonitor

CHECK_INTERVAL = timedelta(hours=23)
LIVE_STATUSES = frozenset({"open", "waiting", "closed", "monitor"})

_CLOSED = (
    r"набор\s+закрыт",
    r"при[ёe]м\s+заявок\s+закрыт",
    r"регистрация\s+закрыта",
    r"набор\s+заверш",
    r"набор\s+не\s+вед",
    r"applications?\s+closed",
    r"registration\s+closed",
    r"набор\s+окончен",
)
_OPEN = (
    r"подать\s+заявку",
    r"отправить\s+заявку",
    r"оставить\s+заявку",
    r"записаться",
    r"регистрация\s+открыта",
    r"набор\s+открыт",
    r"apply\s+now",
    r"податься",
    r"заполнить\s+анкету",
    r"откликнуться",
)
_WAITING = (
    r"скоро\s+откро",
    r"ожидаем",
    r"следите",
    r"анонс",
    r"coming\s+soon",
    r"следующий\s+набор",
    r"жд[её]м",
    r"стартует",
    r"откроется",
    r"будет\s+объявлен",
)
_INTERNSHIP = (
    r"стажиров",
    r"internship",
    r"trainee",
    r"школ",
    r"academy",
    r"camp",
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _html_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.casefold().strip()


def _first_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        found = re.search(pattern, text)
        if found:
            return found.group(0)
    return None


def detect_live_status(html: str, *, fallback: str = "monitor") -> tuple[str, str | None]:
    text = _html_text(html)
    if not text:
        return fallback, None
    hit = _first_match(text, _CLOSED)
    if hit:
        return "closed", hit
    hit = _first_match(text, _OPEN)
    if hit:
        return "open", hit
    hit = _first_match(text, _WAITING)
    if hit:
        return "waiting", hit
    if _first_match(text, _INTERNSHIP):
        return "monitor", "страница про программу, явного набора нет"
    return fallback, None


async def _fetch_page(http: PoliteHttp, program: InternshipProgram) -> str:
    return await http.get_text(program.url, referer=program.url, timeout=25.0)


async def check_program(
    http: PoliteHttp,
    program: InternshipProgram,
    *,
    fallback: str | None = None,
) -> tuple[str, str | None, str | None]:
    seed = fallback or program.catalog_status
    try:
        html = await _fetch_page(http, program)
    except Exception as exc:
        return seed, None, str(exc)[:500]
    status, signal = detect_live_status(html, fallback=seed if seed in LIVE_STATUSES else "monitor")
    return status, signal, None


def _needs_refresh(row: InternshipMonitor | None, *, force: bool) -> bool:
    if force or row is None:
        return True
    return _now() - row.checked_at >= CHECK_INTERVAL


async def refresh_internship_statuses(session: AsyncSession, *, force: bool = False) -> int:
    existing = (
        await session.execute(select(InternshipMonitor))
    ).scalars().all()
    by_slug = {row.program_slug: row for row in existing}
    due = [program for program in PROGRAMS if _needs_refresh(by_slug.get(program.slug), force=force)]
    if not due:
        return 0

    http = PoliteHttp()
    updated = 0
    now = _now()
    for program in due:
        prev = by_slug.get(program.slug)
        fallback = prev.live_status if prev else program.catalog_status
        status, signal, error = await check_program(http, program, fallback=fallback)
        row = prev or InternshipMonitor(program_slug=program.slug, live_status=status, checked_at=now)
        row.live_status = status
        row.signal = signal
        row.check_error = error
        row.checked_at = now
        if prev is None:
            session.add(row)
            by_slug[program.slug] = row
        updated += 1
        await asyncio.sleep(0.2)
    await session.commit()
    return updated


async def monitor_map(session: AsyncSession) -> dict[str, InternshipMonitor]:
    rows = (await session.execute(select(InternshipMonitor))).scalars().all()
    return {row.program_slug: row for row in rows}
