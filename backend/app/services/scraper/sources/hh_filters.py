"""HeadHunter search filters. Site HTML — public API search is 403 since 2026."""

from __future__ import annotations

from urllib.parse import urlencode

from app.services.scraper.sources.geo import CITY_CHOICES, CITY_IDS

HH_ORIGIN = "https://hh.ru"

AREAS = list(CITY_CHOICES)

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


# Hunt formats → HH schedule. All three ≈ no schedule filter.
_HUNT_SCHEDULES = frozenset({"remote", "fullDay", "flexible"})
_ALL_EXPERIENCE = frozenset(item[0] for item in EXPERIENCE)

# Core engineering / analytics / product from HH category 11.
# Not: 121 support, 34 artist/designer, 36 CIO, 126 tech writer — those leak
# sales-adjacent and game-art cards into «весь IT».
IT_PROFESSIONAL_ROLES: tuple[str, ...] = (
    "96",
    "160",
    "124",
    "165",
    "156",
    "148",
    "10",
    "164",
    "150",
    "73",
    "104",
    "116",
    "113",
    "114",
    "112",
    "125",
)

_STACK_ROLES: dict[str, tuple[str, ...]] = {
    "python": ("96",),
    "go": ("96",),
    "java": ("96",),
    "csharp": ("96",),
    "cpp": ("96",),
    "php": ("96",),
    "rust": ("96",),
    "kotlin": ("96",),
    "scala": ("96",),
    "ruby": ("96",),
    "nodejs": ("96",),
    "onec": ("96",),
    "backend": ("96",),
    "frontend": ("96",),
    "fullstack": ("96",),
    "mobile": ("96",),
    "android": ("96",),
    "ios": ("96",),
    "qa": ("124",),
    "devops": ("160",),
    "sre": ("160",),
    "admin": ("113", "114", "112"),
    "security": ("116",),
    "embedded": ("96", "114"),
    "ml": ("165",),
    "data": ("96", "156"),
    "analytics": ("10", "164", "150", "156"),
    "sysanalyst": ("148",),
    "architect": ("104", "96"),
    "product": ("73",),
    "design": ("34", "25", "12"),
}


def roles_for_stack(stack: list[str] | None) -> list[str]:
    picked = [item for item in (stack or []) if item in _STACK_ROLES]
    if not picked or len(picked) >= 8:
        return list(IT_PROFESSIONAL_ROLES)
    out: list[str] = []
    seen: set[str] = set()
    for item in picked:
        for role in _STACK_ROLES[item]:
            if role not in seen:
                seen.add(role)
                out.append(role)
    return out or list(IT_PROFESSIONAL_ROLES)


def normalize_hh_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    experience = [item for item in _as_list(data.get("experience")) if item in _ALL_EXPERIENCE]
    if set(experience) >= _ALL_EXPERIENCE:
        experience = []
    schedule = _as_list(data.get("schedule"))
    if _HUNT_SCHEDULES <= set(schedule):
        schedule = [item for item in schedule if item not in _HUNT_SCHEDULES]
    roles = [
        str(item)
        for item in _as_list(data.get("professional_role") or data.get("professional_roles"))
        if str(item).isdigit()
    ]
    if not roles:
        roles = roles_for_stack(_as_list(data.get("stack")))
    return {
        "search": (data.get("search") or data.get("text") or "").strip(),
        "area": [item for item in _as_list(data.get("area")) if item in CITY_IDS] or ["113"],
        "experience": experience,
        "schedule": schedule,
        "employment": _as_list(data.get("employment")),
        "professional_role": roles,
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
    for role in data["professional_role"]:
        query.append(("professional_role", role))
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
    areas = data["area"]
    if areas == ["113"]:
        parts.append("Россия")
    else:
        for area in areas:
            parts.append(labels.get(area, area))
    roles = data["professional_role"]
    if not roles or set(roles) >= set(IT_PROFESSIONAL_ROLES[:8]):
        parts.append("весь IT")
    if data["schedule"]:
        parts.extend(labels.get(item, item) for item in data["schedule"])
    if data["experience"]:
        parts.extend(labels.get(item, item) for item in data["experience"])
    if data["only_with_salary"]:
        parts.append("с зарплатой")
    unique = list(dict.fromkeys(parts))
    return " · ".join(unique[:5]) or "hh.ru поиск"


def summarize(params: dict) -> str:
    return auto_name(params)
