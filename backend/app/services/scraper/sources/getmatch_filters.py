"""GetMatch listing filters — URL shape from getmatch.ru/vacancies."""

from __future__ import annotations

from urllib.parse import urlencode

GETMATCH_ORIGIN = "https://getmatch.ru"

SPECIALTIES = [
    ("python", "Python"),
    ("golang", "Go"),
    ("java_scala", "Java / Scala"),
    ("js_frontend", "JS / TS"),
    ("js_backend", "Node.js"),
    ("fullstack", "Fullstack"),
    ("qa_auto", "QA Auto"),
    ("qa_manual", "QA Manual"),
    ("dev_ops", "DevOps"),
    ("data_science", "ML / DS"),
    ("android", "Android"),
    ("ios", "iOS"),
    ("c_sharp", "C#"),
    ("php", "PHP"),
    ("kotlin", "Kotlin"),
    ("system_analyst", "Системный аналитик"),
    ("product_management", "Product"),
]

LOCATIONS = [
    ("remote", "удалённо"),
    ("moscow", "Москва"),
    ("saint_petersburg", "Санкт-Петербург"),
]

LEVELS = [
    ("junior", "junior"),
    ("middle", "middle"),
    ("senior", "senior"),
    ("lead", "lead"),
    ("c-level", "c-level"),
]

SALARIES = [
    (0, "любая"),
    (150000, "от 150 000"),
    (200000, "от 200 000"),
    (250000, "от 250 000"),
    (350000, "от 350 000"),
]


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def normalize_getmatch_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    allowed_sp = {item[0] for item in SPECIALTIES}
    allowed_loc = {item[0] for item in LOCATIONS}
    allowed_lvl = {item[0] for item in LEVELS}
    specialties = [
        item
        for item in _as_list(data.get("specialties") or data.get("specialty") or data.get("sp"))
        if item in allowed_sp
    ]
    unique_sp: list[str] = []
    seen_sp: set[str] = set()
    for item in specialties:
        if item not in seen_sp:
            seen_sp.add(item)
            unique_sp.append(item)
    specialties = unique_sp
    specialty = specialties[0] if specialties else ""
    location = str(data.get("location") or data.get("l") or "").strip()
    if location not in allowed_loc:
        location = ""
    levels = [item for item in _as_list(data.get("level") or data.get("g")) if item in allowed_lvl]
    salary = data.get("salary") or data.get("salary_from") or 0
    try:
        salary_n = int(salary)
    except (TypeError, ValueError):
        salary_n = 0
    return {
        "search": (data.get("search") or data.get("q") or "").strip(),
        "specialty": specialty,
        "specialties": specialties,
        "location": location,
        "level": levels,
        "salary": salary_n if salary_n > 0 else 0,
    }


def listing_url_from_params(params: dict, *, specialty: str | None = None) -> str:
    data = normalize_getmatch_params(params)
    query: list[tuple[str, str]] = []
    sp = specialty if specialty is not None else data["specialty"]
    if sp:
        query.append(("sp", sp))
    if data["location"]:
        query.append(("l", data["location"]))
    for level in data["level"]:
        query.append(("g", level))
    if data["salary"]:
        query.append(("salary_from", str(data["salary"])))
    if data["search"]:
        query.append(("q", data["search"]))
    encoded = urlencode(query, doseq=True)
    path = f"{GETMATCH_ORIGIN}/vacancies"
    return f"{path}?{encoded}" if encoded else path


def auto_name(params: dict) -> str:
    data = normalize_getmatch_params(params)
    labels = {
        **dict(SPECIALTIES),
        **dict(LOCATIONS),
    }
    parts: list[str] = []
    if data["search"]:
        parts.append(data["search"])
    specialties = data.get("specialties") or ([data["specialty"]] if data["specialty"] else [])
    if len(specialties) >= 8:
        parts.append("все специальности")
    elif len(specialties) > 1:
        parts.append(f"{len(specialties)} специальностей")
    elif specialties:
        parts.append(labels.get(specialties[0], specialties[0]))
    if data["location"]:
        parts.append(labels.get(data["location"], data["location"]))
    parts.extend(data["level"])
    if data["salary"]:
        parts.append(f"от {data['salary']}")
    unique = list(dict.fromkeys(parts))
    return " · ".join(unique[:5]) or "GetMatch поиск"
