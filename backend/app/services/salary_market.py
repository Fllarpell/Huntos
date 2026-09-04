"""Salary market over the full scraped pool + Habr / GetMatch / Levels.fyi benchmarks."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.vacancy import Vacancy
from app.services.getmatch_salaries import fetch_getmatch_salaries
from app.services.habr_salaries import fetch_habr_salaries
from app.services.hh_salaries import fetch_hh_career_salaries, hh_overall_from_rows
from app.services.levels_fyi import fetch_levels_benchmarks
from app.services.salary_aggregators import levels_as_aggregators
from app.services.salary_fallback import bundled_aggregators
from app.services.salary_stats import (
    CORRIDOR_MIN_N,
    corridor_from_vacancies,
    filter_options,
    filter_salary_rows,
)

CACHE_NAME = "levels_fyi_benchmarks.json"
HABR_CACHE_NAME = "habr_salaries.json"
GETMATCH_CACHE_NAME = "getmatch_salaries.json"
HH_CACHE_NAME = "hh_career_salaries.json"
CACHE_TTL = timedelta(hours=24)
MARKET_LIMIT = 5000


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _json_cache(path: Path, *, allow_stale: bool = True) -> list[dict] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched = payload.get("fetched_at")
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        return None
    if fetched and not allow_stale:
        try:
            at = datetime.fromisoformat(str(fetched).replace("Z", ""))
            if _now() - at > CACHE_TTL:
                return None
        except ValueError:
            return None
    return rows


def _save_json_cache(path: Path, items: list[dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"fetched_at": _now().isoformat() + "Z", "items": items}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _cache_path() -> Path:
    base = Path(getattr(settings, "data_dir", None) or "/data")
    if not base.exists():
        base = Path("/tmp")
    return base / CACHE_NAME


def _habr_cache_path() -> Path:
    return _cache_path().with_name(HABR_CACHE_NAME)


def _getmatch_cache_path() -> Path:
    return _cache_path().with_name(GETMATCH_CACHE_NAME)


def _hh_cache_path() -> Path:
    return _cache_path().with_name(HH_CACHE_NAME)


def load_levels_cache() -> list[dict] | None:
    return _json_cache(_cache_path())


def save_levels_cache(items: list[dict]) -> None:
    _save_json_cache(_cache_path(), items)


def load_habr_salaries_cache() -> list[dict] | None:
    return _json_cache(_habr_cache_path())


def save_habr_salaries_cache(items: list[dict]) -> None:
    _save_json_cache(_habr_cache_path(), items)


def load_getmatch_salaries_cache() -> list[dict] | None:
    return _json_cache(_getmatch_cache_path())


def save_getmatch_salaries_cache(items: list[dict]) -> None:
    _save_json_cache(_getmatch_cache_path(), items)


def load_hh_salaries_cache() -> list[dict] | None:
    return _json_cache(_hh_cache_path())


def save_hh_salaries_cache(items: list[dict]) -> None:
    _save_json_cache(_hh_cache_path(), items)


async def refresh_levels_cache(http=None) -> dict:
    items, errors = await fetch_levels_benchmarks(http=http)
    if items:
        save_levels_cache(items)
    return {"count": len(items), "errors": len(errors), "items": items, "error_detail": errors[:5]}


async def refresh_habr_salaries_cache(http=None) -> dict:
    items, errors = await fetch_habr_salaries(http=http)
    if items:
        save_habr_salaries_cache(items)
    return {"count": len(items), "errors": len(errors), "items": items, "error_detail": errors[:5]}


async def refresh_getmatch_salaries_cache(http=None) -> dict:
    items, errors = await fetch_getmatch_salaries(http=http)
    if items:
        save_getmatch_salaries_cache(items)
    return {"count": len(items), "errors": len(errors), "items": items, "error_detail": errors[:5]}


async def refresh_hh_salaries_cache(http=None) -> dict:
    items, errors = await fetch_hh_career_salaries(http=http)
    if items:
        save_hh_salaries_cache(items)
    return {"count": len(items), "errors": len(errors), "items": items, "error_detail": errors[:5]}


async def refresh_salary_benchmarks(http=None) -> dict:
    levels = await refresh_levels_cache(http=http)
    habr = await refresh_habr_salaries_cache(http=http)
    getmatch = await refresh_getmatch_salaries_cache(http=http)
    hh = await refresh_hh_salaries_cache(http=http)
    return {"levels_fyi": levels, "habr_career": habr, "getmatch": getmatch, "hh_career": hh}


def _overlay_aggregators(*groups: list[dict] | None) -> list[dict]:
    """Later groups win on the same key. Bundled priors stay if a donor is empty."""
    by_key: dict[str, dict] = {}
    extras: list[dict] = []
    for group in groups:
        for row in group or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "").strip()
            if key:
                by_key[key] = row
            else:
                extras.append(row)
    return list(by_key.values()) + extras


async def _user_salary_rows(session: AsyncSession, user_id: int) -> list[Vacancy]:
    """Every vacancy with a fork — all sources, career sites, boards."""
    rows = (
        await session.execute(
            select(Vacancy)
            .where(
                Vacancy.user_id == user_id,
                or_(Vacancy.salary_min.is_not(None), Vacancy.salary_max.is_not(None)),
            )
            .limit(MARKET_LIMIT)
        )
    ).scalars().all()
    return list(rows)


async def build_salary_market(
    session: AsyncSession,
    user_id: int,
    *,
    sample_rows: list | None = None,
    grade: str | None = None,
    specialty: str | None = None,
    refresh_levels: bool = False,
) -> dict:
    """Market corridor: vacancy forks if any, otherwise public aggregators."""
    all_rows = await _user_salary_rows(session, user_id)
    if refresh_levels:
        await refresh_salary_benchmarks()

    live = [
        *(load_habr_salaries_cache() or []),
        *(load_getmatch_salaries_cache() or []),
        *levels_as_aggregators(load_levels_cache()),
        *(load_hh_salaries_cache() or []),
    ]
    aggregators = _overlay_aggregators(bundled_aggregators(), live)
    hh_mix = hh_overall_from_rows(aggregators)
    if hh_mix:
        aggregators = [row for row in aggregators if row.get("key") != "hh_career_all"]
        aggregators.append(hh_mix)

    habr = [row for row in aggregators if row.get("source") == "habr_career"]
    getmatch = [row for row in aggregators if row.get("source") == "getmatch_salaries"]
    hh = [row for row in aggregators if row.get("source") == "hh_career"]
    levels = load_levels_cache() or []
    live_levels = [row for row in aggregators if row.get("source") == "levels.fyi"]
    if not levels and live_levels:
        levels = [
            {
                "key": row.get("key"),
                "label": row.get("label"),
                "url": row.get("url"),
                "source": "levels.fyi",
                "attribution": row.get("attribution"),
                "monthly": {
                    "p25": row.get("p25"),
                    "median": row.get("median"),
                    "p75": row.get("p75"),
                    "period": "month",
                },
            }
            for row in live_levels
        ]
    market = corridor_from_vacancies(all_rows, grade=grade, specialty=specialty, aggregators=aggregators)

    # Option lists follow the complementary filter so dropdowns stay useful.
    grade_pool = filter_salary_rows(all_rows, specialty=specialty)
    specialty_pool = filter_salary_rows(all_rows, grade=grade)
    grades = filter_options(
        corridor_from_vacancies(grade_pool, specialty=specialty, aggregators=aggregators),
        min_n=CORRIDOR_MIN_N,
    )["grades"]
    specialties = filter_options(
        corridor_from_vacancies(specialty_pool, grade=grade, aggregators=aggregators),
        min_n=CORRIDOR_MIN_N,
    )["specialties"]

    sample = (
        corridor_from_vacancies(sample_rows or [], grade=grade, specialty=specialty, aggregators=aggregators)
        if sample_rows is not None
        else market
    )

    return {
        "market": market,
        # aliases for older clients
        "platforms": market,
        "sample": sample,
        "open_boards": market,
        "filters": {
            "grade": market.get("grade"),
            "specialty": market.get("specialty"),
            "grades": grades,
            "specialties": specialties,
        },
        "aggregators": aggregators,
        "levels_fyi": levels or [],
        "levels_meta": {"cached": True, "errors": 0},
        "habr_career": habr or [],
        "habr_meta": {"cached": True, "errors": 0},
        "getmatch": getmatch or [],
        "getmatch_meta": {"cached": True, "errors": 0},
        "hh_career": hh or [],
        "hh_meta": {"cached": True, "errors": 0},
        "method": {
            "market": "p25 / медиана / p75: вилки вакансий + зарплатные агрегаторы (Хабр Карьера, GetMatch, hh.ru профессии, Levels.fyi).",
            "filters": "Грейд и специальность — срезы той же смеси вакансий и агрегаторов.",
            "levels_fyi": "Официальные .md Levels.fyi (Russia/Moscow). Годовой TC; месяц ≈ /12.",
            "habr_career": "Хабр Карьера /salaries — вилки по анкетам (месяц, RUB).",
            "getmatch": "GetMatch /api/salaries — публичный общий срез (p25 / медиана / p90).",
            "hh_career": "career.hh.ru/profession — медианы зарплат в вакансиях hh по IT-профессиям.",
        },
        "updated_at": _now().isoformat() + "Z",
    }
