"""HireHi listing filters — values taken from the site's own search UI/API."""

from __future__ import annotations

CATEGORIES = [
    ("development", "Разработка"),
    ("devops", "DevOps"),
    ("qa", "Тестирование"),
    ("analytics", "Аналитика"),
    ("design", "Дизайн"),
    ("management", "Менеджмент"),
    ("marketing", "Маркетинг"),
    ("sales", "Продажи"),
    ("finance", "Финансы"),
    ("recruiting", "Рекрутинг"),
]

SUBCATEGORIES = [
    ("ml_ai", "ML/AI"),
    ("python", "Python"),
    ("java", "Java"),
    ("backend", "Backend"),
    ("go", "Go"),
    ("data_engineer", "Data Engineer"),
    ("frontend", "Frontend"),
    ("fullstack", "Fullstack"),
    ("netc", ".NET/C#"),
    ("cpp", "C++"),
    ("php", "PHP"),
    ("nodejs", "Node.js"),
    ("kotlin", "Kotlin"),
    ("rust", "Rust"),
    ("mobile", "Mobile"),
    ("android", "Android"),
    ("ios", "iOS"),
    ("onec", "1C"),
    ("erp_crm", "ERP / CRM"),
]

FORMATS = [
    ("удалённо", "удалённо"),
    ("офис", "офис"),
    ("гибрид", "гибрид"),
    ("удалённо по РФ", "удалённо по РФ"),
]

LEVELS = [
    ("intern", "intern"),
    ("junior", "junior"),
    ("middle", "middle"),
    ("senior", "senior"),
    ("lead", "lead"),
    ("head", "head"),
]

ENGLISH = [
    ("english", "нужен английский"),
    ("no_english", "не нужен английский"),
]

CONTACTS = [
    ("direct_contact", "прямой контакт"),
    ("linkedin", "LinkedIn"),
    ("email", "Email"),
    ("telegram", "Telegram"),
]

SORTS = [
    ("date", "сначала новые"),
    ("salary_desc", "больше денег"),
]

_LIST_KEYS = (
    "format",
    "level",
    "subcategory",
    "english",
    "direct_contact",
    "salary",
    "country",
    "region",
    "industry",
)


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def normalize_hirehi_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    return {
        "category": data.get("category") or "development",
        "search": (data.get("search") or "").strip(),
        "sort": data.get("sort") or "date",
        "format": _as_list(data.get("format")),
        "level": _as_list(data.get("level")),
        "subcategory": _as_list(data.get("subcategory")),
        "english": _as_list(data.get("english")),
        "direct_contact": _as_list(data.get("direct_contact")),
        "salary": _as_list(data.get("salary")),
        "country": _as_list(data.get("country")),
        "region": _as_list(data.get("region")),
        "industry": _as_list(data.get("industry")),
        "city": (data.get("city") or "").strip(),
    }


def auto_name(params: dict) -> str:
    labels = dict(SUBCATEGORIES)
    parts: list[str] = []
    search = (params.get("search") or "").strip()
    if search:
        parts.append(search)
    for slug in params.get("subcategory") or []:
        label = labels.get(slug, slug)
        if label.lower() != search.lower():
            parts.append(label)
    parts.extend(params.get("format") or [])
    levels = params.get("level") or []
    if levels:
        parts.append(", ".join(levels))
    english = params.get("english") or []
    if "english" in english:
        parts.append("EN")
    if "no_english" in english:
        parts.append("без EN")
    unique = list(dict.fromkeys(parts))
    return " · ".join(unique[:5]) or "HireHi поиск"
