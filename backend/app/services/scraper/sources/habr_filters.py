"""Habr Career search filters — RSS query params from career.habr.com."""

from __future__ import annotations

from urllib.parse import urlencode

HABR_ORIGIN = "https://career.habr.com"

QUALIFICATIONS = [
    ("1", "intern"),
    ("3", "junior"),
    ("4", "middle"),
    ("5", "senior"),
    ("6", "lead"),
]

SPECIALIZATIONS = [
    ("2", "Backend"),
    ("3", "Frontend"),
    ("4", "Fullstack"),
    ("5", "Mobile"),
    ("10", "QA Auto"),
    ("12", "QA Manual"),
    ("22", "DevOps"),
    ("41", "Системный аналитик"),
    ("43", "Data Analyst"),
    ("44", "Data Scientist"),
    ("76", "Data Engineer"),
    ("73", "Архитектор"),
    ("7", "Embedded"),
]


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def normalize_habr_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    salary = data.get("salary") or 0
    try:
        salary_n = int(salary)
    except (TypeError, ValueError):
        salary_n = 0
    qid = str(data.get("qid") or data.get("qualification") or "").strip()
    allowed_qid = {item[0] for item in QUALIFICATIONS}
    if qid not in allowed_qid:
        qid = ""
    allowed_s = {item[0] for item in SPECIALIZATIONS}
    specs = [item for item in _as_list(data.get("s") or data.get("specializations")) if item in allowed_s]
    return {
        "search": (data.get("search") or data.get("q") or "").strip(),
        "remote": bool(data.get("remote")),
        "qid": qid,
        "s": specs,
        "with_salary": bool(data.get("with_salary")),
        "salary": salary_n if salary_n > 0 else 0,
    }


def listing_url_from_params(params: dict) -> str:
    data = normalize_habr_params(params)
    query: list[tuple[str, str]] = []
    if data["search"]:
        query.append(("q", data["search"]))
    if data["remote"]:
        query.append(("remote", "true"))
    if data["qid"]:
        query.append(("qid", data["qid"]))
    for spec in data["s"]:
        query.append(("s[]", spec))
    if data["with_salary"]:
        query.append(("with_salary", "true"))
    if data["salary"]:
        query.append(("salary", str(data["salary"])))
        query.append(("currency", "rur"))
    encoded = urlencode(query, doseq=True)
    path = f"{HABR_ORIGIN}/vacancies"
    return f"{path}?{encoded}" if encoded else path


def rss_url_from_params(params: dict, *, page: int = 1) -> str:
    html_url = listing_url_from_params(params)
    if "?" in html_url:
        url = html_url.replace("/vacancies?", "/vacancies/rss?", 1)
    else:
        url = f"{HABR_ORIGIN}/vacancies/rss"
    if page > 1:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}page={page}"
    return url


def api_url_from_params(params: dict, *, page: int = 1, per_page: int = 25) -> str:
    data = normalize_habr_params(params)
    query: list[tuple[str, str]] = [("sort", "date"), ("page", str(max(1, page))), ("per_page", str(per_page))]
    if data["search"]:
        query.append(("q", data["search"]))
    if data["remote"]:
        query.append(("remote", "true"))
    if data["qid"]:
        query.append(("qid", data["qid"]))
    for spec in data["s"]:
        query.append(("s[]", spec))
    if data["with_salary"]:
        query.append(("with_salary", "true"))
    if data["salary"]:
        query.append(("salary", str(data["salary"])))
        query.append(("currency", "RUR"))
    return f"{HABR_ORIGIN}/api/frontend/vacancies?{urlencode(query, doseq=True)}"


def auto_name(params: dict) -> str:
    data = normalize_habr_params(params)
    labels = dict(SPECIALIZATIONS)
    grades = dict(QUALIFICATIONS)
    parts: list[str] = []
    if data["search"]:
        parts.append(data["search"])
    specs = data["s"]
    if len(specs) >= 8:
        parts.append("весь IT")
    else:
        for spec in specs:
            parts.append(labels.get(spec, spec))
    if data["remote"]:
        parts.append("удалённо")
    if data["qid"]:
        parts.append(grades.get(data["qid"], data["qid"]))
    if data["salary"]:
        parts.append(f"от {data['salary']}")
    unique = list(dict.fromkeys(parts))
    return " · ".join(unique[:5]) or "Habr Career поиск"
