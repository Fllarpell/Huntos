"""Habr Career salary report (career.habr.com/salaries) — public Nuxt payload."""

from __future__ import annotations

import json
import re
from typing import Any

HABR_SALARIES_URL = "https://career.habr.com/salaries"
HABR_ORIGIN = "https://career.habr.com"

_SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.I | re.S)

_GRADE = {
    "all": "all",
    "intern": "intern",
    "junior": "junior",
    "middle": "middle",
    "senior": "senior",
    "lead": "lead",
}


def _deref(payload: list, value: Any, *, depth: int = 0) -> Any:
    if depth > 24:
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int) and 0 <= value < len(payload):
        slot = payload[value]
        if slot is value:
            return value
        return _deref(payload, slot, depth=depth + 1)
    return value


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if number > 0 else None
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            return None
        try:
            number = int(digits)
        except ValueError:
            return None
        return number if number > 0 else None
    return None


def parse_habr_salary_rows(payload: list) -> list[dict]:
    """Pull grade corridors out of the dehydrated Nuxt payload."""
    rows: list[dict] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        if not {"name", "median", "p25", "p75"} <= item.keys():
            continue
        name = str(_deref(payload, item.get("name")) or "").strip()
        grade = _GRADE.get(name.lower())
        if grade is None:
            continue
        if grade in seen:
            continue
        p25 = _as_int(_deref(payload, item.get("p25")))
        median = _as_int(_deref(payload, item.get("median")))
        p75 = _as_int(_deref(payload, item.get("p75")))
        if p25 is None or median is None or p75 is None:
            continue
        n = _as_int(_deref(payload, item.get("total")))
        title = str(_deref(payload, item.get("title")) or name).strip()
        seen.add(grade)
        rows.append(
            {
                "key": f"habr_{grade}",
                "grade": None if grade == "all" else grade,
                "label": "IT · все грейды" if grade == "all" else f"IT · {name}",
                "title": title,
                "n": n,
                "p25": p25,
                "median": median,
                "p75": p75,
                "min": _as_int(_deref(payload, item.get("min"))),
                "max": _as_int(_deref(payload, item.get("max"))),
                "currency": "RUB",
                "period": "month",
                "source": "habr_career",
                "url": HABR_SALARIES_URL,
                "attribution": "Хабр Карьера · зарплаты (анкеты специалистов)",
            }
        )
    order = ["all", "intern", "junior", "middle", "senior", "lead"]
    rows.sort(key=lambda row: order.index(row["grade"] or "all") if (row["grade"] or "all") in order else 99)
    return rows


def parse_habr_salaries_html(html: str) -> list[dict]:
    for script in _SCRIPT.findall(html or ""):
        text = (script or "").strip()
        if len(text) < 200 or not text.startswith("["):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, list) or len(payload) < 3:
            continue
        rows = parse_habr_salary_rows(payload)
        if rows:
            return rows
    return []


async def fetch_habr_salaries(http=None) -> tuple[list[dict], list[str]]:
    from app.services.scraper.http import PoliteHttp

    client = http or PoliteHttp()
    errors: list[str] = []
    try:
        html = await client.get_text(HABR_SALARIES_URL, referer=HABR_ORIGIN)
    except Exception as exc:  # noqa: BLE001 — donor page, keep the rest of market
        return [], [str(exc)]
    rows = parse_habr_salaries_html(html)
    if not rows:
        errors.append("habr salaries: empty payload")
    return rows, errors
