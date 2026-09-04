"""hh.ru Career profession medians (career.hh.ru/profession/{id}) — vacancy-based."""

from __future__ import annotations

import re
from html import unescape

HH_CAREER_ORIGIN = "https://career.hh.ru"

# Public profession pages in «Разработка ПО» and adjacent IT. Median = posted vacancy salaries.
HH_PROFESSIONS: tuple[dict, ...] = (
    {"id": 50, "specialty": "python", "label": "Python-разработчик"},
    {"id": 38, "specialty": "java", "label": "Java-разработчик"},
    {"id": 46, "specialty": "go", "label": "Golang-разработчик"},
    {"id": 45, "specialty": "csharp", "label": "C#/.NET-разработчик"},
    {"id": 41, "specialty": "ruby", "label": "Ruby-разработчик"},
    {"id": 49, "specialty": "php", "label": "PHP-разработчик"},
    {"id": 40, "specialty": "frontend", "label": "Frontend-разработчик"},
    {"id": 43, "specialty": "backend", "label": "Backend-разработчик"},
    {"id": 44, "specialty": "fullstack", "label": "Fullstack-разработчик"},
    {"id": 42, "specialty": "android", "label": "Android-разработчик"},
    {"id": 47, "specialty": "ios", "label": "iOS-разработчик"},
    {"id": 52, "specialty": "mobile", "label": "Flutter-разработчик"},
    {"id": 53, "specialty": "devops", "label": "DevOps-инженер"},
    {"id": 1, "specialty": "ml_ai", "label": "Data Scientist"},
    {"id": 7, "specialty": "data_engineer", "label": "Data Engineer"},
    {"id": 5, "specialty": "analytics", "label": "BI-аналитик"},
    {"id": 57, "specialty": "backend", "label": "Инженер-программист"},
    {"id": 96, "specialty": "backend", "label": "Архитектор ПО"},
    {"id": 95, "specialty": "qa", "label": "Нагрузочное тестирование"},
)

_H2_MONEY = re.compile(
    r"<h2[^>]*>\s*([0-9][0-9\s\u00a0\u202f]*)\s*₽\s*</h2>",
    re.I | re.S,
)
_LD_NAME = re.compile(
    r'"@type"\s*:\s*"ListItem"\s*,\s*"position"\s*:\s*3\s*,\s*"name"\s*:\s*"([^"]+)"',
    re.I,
)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _digits(raw: str) -> int | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    try:
        number = int(digits)
    except ValueError:
        return None
    return number if number > 0 else None


def parse_hh_profession_html(html: str, *, meta: dict) -> dict | None:
    """Median from the profession salary chart (first large ₽ heading)."""
    blob = unescape(html or "")
    amounts: list[int] = []
    for match in _H2_MONEY.finditer(blob):
        number = _digits(match.group(1))
        if number is not None and 30_000 <= number <= 900_000:
            amounts.append(number)
    if not amounts:
        return None
    median = amounts[0]
    ld = _LD_NAME.search(blob)
    title_m = _TITLE.search(blob)
    label = (meta.get("label") or "").strip()
    if ld:
        label = re.sub(r"^[⭐️\s]+", "", ld.group(1)).strip() or label
    elif title_m and not label:
        label = re.sub(r"\s+", " ", title_m.group(1)).split(":")[0].strip()
    pid = int(meta["id"])
    return {
        "key": f"hh_career_{pid}",
        "grade": None,
        "specialty": meta.get("specialty"),
        "label": label or meta.get("label") or f"profession {pid}",
        "n": None,
        "p25": None,
        "median": median,
        "p75": None,
        "currency": "RUB",
        "period": "month",
        "source": "hh_career",
        "url": f"{HH_CAREER_ORIGIN}/profession/{pid}",
        "attribution": "hh.ru · медианы зарплат в вакансиях (career.hh.ru)",
        "mix": True,
    }


def hh_overall_from_rows(rows: list[dict] | None) -> dict | None:
    """p25 / median / p75 across profession medians — not a single language."""
    from app.services.salary_stats import percentile

    medians: list[int] = []
    for row in rows or []:
        if (row.get("source") or "hh_career") != "hh_career":
            continue
        if not (row.get("specialty") or "").strip():
            continue
        raw = row.get("median")
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number > 0:
            medians.append(number)
    if len(medians) < 3:
        return None
    return {
        "key": "hh_career_all",
        "grade": None,
        "specialty": None,
        "label": "IT-профессии",
        "n": len(medians),
        "p25": percentile(medians, 25),
        "median": percentile(medians, 50),
        "p75": percentile(medians, 75),
        "currency": "RUB",
        "period": "month",
        "source": "hh_career",
        "url": f"{HH_CAREER_ORIGIN}/professions",
        "attribution": "hh.ru · медианы зарплат в вакансиях (career.hh.ru)",
        "mix": True,
    }


async def fetch_hh_career_salaries(http=None) -> tuple[list[dict], list[str]]:
    from app.services.scraper.http import PoliteHttp

    client = http or PoliteHttp()
    errors: list[str] = []
    rows: list[dict] = []
    for meta in HH_PROFESSIONS:
        url = f"{HH_CAREER_ORIGIN}/profession/{meta['id']}"
        try:
            html = await client.get_text(url, referer=f"{HH_CAREER_ORIGIN}/professions")
        except Exception as exc:  # noqa: BLE001 — one profession must not kill the rest
            errors.append(f"{meta['id']}: {exc}"[:240])
            continue
        parsed = parse_hh_profession_html(html, meta=meta)
        if not parsed:
            errors.append(f"{meta['id']}: empty parse")
            continue
        rows.append(parsed)
    return rows, errors
