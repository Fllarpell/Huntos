"""HeadHunter search filters. Site HTML — public API search is 403 since 2026."""

from __future__ import annotations

from urllib.parse import urlencode

HH_ORIGIN = "https://hh.ru"

AREAS = [
    ("1", "Москва"),
    ("2", "Санкт-Петербург"),
    ("113", "Россия"),
    ("3", "Екатеринбург"),
    ("4", "Новосибирск"),
    ("88", "Казань"),
    ("66", "Нижний Новгород"),
]

EXPERIENCE = [
    ("noExperience", "без опыта"),
    ("between1And3", "1–3 года"),
    ("between3And6", "3–6 лет"),
    ("moreThan6", "6+ лет"),
]

SCHEDULE = [
    ("remote", "удалённо"),
    ("fullDay", "полный день"),
    ("flexible", "гибкий"),
    ("shift", "смены"),
    ("flyInFlyOut", "вахта"),
]

EMPLOYMENT = [
    ("full", "полная"),
    ("part", "частичная"),
    ("project", "проект"),
    ("probation", "стажировка"),
]

SORTS = [
    ("publication_time", "сначала новые"),
    ("salary_desc", "больше денег"),
    ("relevance", "по соответствию"),
]

PERIODS = [
    ("", "за всё время"),
    ("1", "за сутки"),
    ("3", "за 3 дня"),
    ("7", "за неделю"),
    ("30", "за месяц"),
]


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def normalize_hh_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    return {
        "search": (data.get("search") or data.get("text") or "").strip(),
        "area": _as_list(data.get("area")) or ["1"],
        "experience": _as_list(data.get("experience")),
        "schedule": _as_list(data.get("schedule")),
        "employment": _as_list(data.get("employment")),
        "order_by": data.get("order_by") or "publication_time",
        "search_period": str(data.get("search_period") or ""),
        "only_with_salary": bool(data.get("only_with_salary")),
        "headed": bool(data.get("headed")),
    }


def listing_url_from_params(params: dict, *, page: int = 0) -> str:
    data = normalize_hh_params(params)
    query: list[tuple[str, str]] = []
    if data["search"]:
        query.append(("text", data["search"]))
    for area in data["area"]:
        query.append(("area", area))
    for item in data["experience"]:
        query.append(("experience", item))
    for item in data["schedule"]:
        query.append(("schedule", item))
    for item in data["employment"]:
        query.append(("employment", item))
    if data["order_by"]:
        query.append(("order_by", data["order_by"]))
    if data["search_period"]:
        query.append(("search_period", data["search_period"]))
    if data["only_with_salary"]:
        query.append(("only_with_salary", "true"))
    query.append(("items_on_page", "50"))
    if page > 0:
        query.append(("page", str(page)))
    return f"{HH_ORIGIN}/search/vacancy?{urlencode(query, doseq=True)}"


def auto_name(params: dict) -> str:
    data = normalize_hh_params(params)
    labels = {
        **dict(AREAS),
        **dict(EXPERIENCE),
        **dict(SCHEDULE),
        **dict(EMPLOYMENT),
    }
    parts: list[str] = []
    if data["search"]:
        parts.append(data["search"])
    for area in data["area"]:
        parts.append(labels.get(area, area))
    for item in data["schedule"]:
        parts.append(labels.get(item, item))
    for item in data["experience"]:
        parts.append(labels.get(item, item))
    unique = list(dict.fromkeys(parts))
    return " · ".join(unique[:5]) or "hh.ru поиск"


def summarize(params: dict) -> str:
    return auto_name(params)
