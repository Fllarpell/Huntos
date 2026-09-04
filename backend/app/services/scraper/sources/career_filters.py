"""Career board subscribe params and local listing filters."""

from __future__ import annotations

from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.career_catalog import YANDEX_IT_PROFESSIONS, get_board
from app.services.scraper.sources.geo import CITY_IDS, location_hits_cities
from app.services.scraper.sources.it_job_gate import is_non_it_title, looks_like_it_job
from app.services.scraper.sources.stack_lexicon import STACK_IDS, stack_hits

_FORMATS = ("remote", "office", "hybrid")
_LEVELS = ("intern", "junior", "middle", "senior", "lead", "head")

_FORMAT_WORDS = {
    "remote": ("удал", "remote", "дистанц", "из дома", "from home"),
    "office": ("офис", "office", "из офиса"),
    "hybrid": ("гибрид", "hybrid", "mixed", "гибк", "офис/удал"),
}

_STACK = STACK_IDS

# Fetch adapter only: Hunt stack chips → Yandex Jobs API profession slugs.
# Matching on every board (VK, Megafon, YADRO, T-Bank, Avito, …) uses stack_lexicon.
YANDEX_STACK_PROFESSIONS: dict[str, tuple[str, ...]] = {
    "python": ("backend-developer",),
    "go": ("backend-developer", "system-developer"),
    "java": ("backend-developer",),
    "csharp": ("backend-developer",),
    "cpp": ("system-developer", "backend-developer"),
    "php": ("backend-developer",),
    "rust": ("system-developer", "backend-developer"),
    "kotlin": ("backend-developer", "mob-app-developer", "mob-app-developer-android"),
    "scala": ("backend-developer",),
    "ruby": ("backend-developer",),
    "nodejs": ("backend-developer", "full-stack-developer"),
    "backend": ("backend-developer",),
    "frontend": ("frontend-developer",),
    "fullstack": ("full-stack-developer",),
    "mobile": ("mob-app-developer", "mob-app-developer-android", "mob-app-developer-ios"),
    "android": ("mob-app-developer-android", "mob-app-developer"),
    "ios": ("mob-app-developer-ios", "mob-app-developer"),
    "qa": ("tester-auto", "tester-manual", "test-developer"),
    "devops": ("dev-ops", "system-developer"),
    "sre": ("dev-ops", "system-developer"),
    "admin": ("sys-admin", "database-admin"),
    "security": ("information-security",),
    "embedded": ("system-developer", "desktop-developer"),
    "ml": ("ml-developer", "ml-researcher"),
    "data": ("data-engineer", "database-developer", "database-admin"),
    "analytics": ("analyst", "analyst-developer", "system-analyst"),
    "sysanalyst": ("system-analyst",),
    "architect": ("solutions-architect", "backend-developer", "system-developer"),
    "product": ("product-manager",),
    "design": ("designer-uxui", "designer"),
}


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _as_int(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def normalize_career_params(raw: dict | None) -> dict:
    data = dict(raw or {})
    slug = str(data.get("company") or data.get("slug") or "").strip().lower()
    board = get_board(slug)
    out: dict = {"company": board.slug if board else ""}
    search = str(data.get("search") or "").strip()
    if search:
        out["search"] = search
    formats = [item for item in _as_list(data.get("formats") or data.get("format")) if item in _FORMATS]
    if formats:
        out["formats"] = sorted(set(formats))
    levels = [item for item in _as_list(data.get("levels") or data.get("level")) if item in _LEVELS]
    if levels:
        out["levels"] = sorted(set(levels))
    stack = [item for item in _as_list(data.get("stack")) if item in _STACK]
    if stack:
        out["stack"] = sorted(set(stack))
    cities = [item for item in _as_list(data.get("cities") or data.get("city")) if item in CITY_IDS]
    if cities:
        out["cities"] = sorted(set(cities))
    if data.get("only_salary") or data.get("onlySalary"):
        out["only_salary"] = True
    salary = _as_int(data.get("salary_from") or data.get("salaryFrom") or data.get("salary"))
    if salary:
        out["salary_from"] = salary
    return out


def listing_url_from_params(params: dict) -> str:
    board = get_board(normalize_career_params(params)["company"])
    return board.listing_url if board else ""


def auto_name(params: dict) -> str:
    data = normalize_career_params(params)
    board = get_board(data["company"])
    parts = [board.name if board else "сайт компании"]
    if data.get("search"):
        parts.append(str(data["search"]))
    stack = data.get("stack") or []
    if stack:
        if len(stack) >= max(8, len(_STACK) - 4):
            parts.append("весь IT")
        else:
            parts.extend(str(item) for item in stack[:3])
            if len(stack) > 3:
                parts.append(f"+{len(stack) - 3}")
    if data.get("formats") and len(parts) < 5:
        labels = {"remote": "удалённо", "office": "офис", "hybrid": "гибрид"}
        formats = data["formats"]
        if len(formats) >= 3:
            pass  # все форматы — не засоряем имя
        else:
            parts.extend(labels.get(item, item) for item in formats)
    return " · ".join(parts[:6])


def _stack_is_wide(stack: list[str]) -> bool:
    return len(stack) >= max(8, len(_STACK) - 4)


def yandex_professions(params: dict) -> tuple[str, ...]:
    stack = normalize_career_params(params).get("stack") or []
    if _stack_is_wide(stack):
        # Too many professions → Yandex API returns empty; omit filter.
        return ()
    picked: list[str] = []
    seen: set[str] = set()
    for item in stack:
        for profession in YANDEX_STACK_PROFESSIONS.get(item, ()):
            if profession not in seen:
                seen.add(profession)
                picked.append(profession)
    return tuple(picked) if picked else YANDEX_IT_PROFESSIONS


def _blob(job: dict) -> str:
    skills = job.get("skills") or []
    if isinstance(skills, str):
        skill_text = skills
    else:
        skill_text = " ".join(str(item) for item in skills)
    parts = [
        job.get("title"),
        job.get("specialty"),
        job.get("team"),
        job.get("location"),
        job.get("work_format"),
        job.get("short_summary"),
        job.get("description"),
        skill_text,
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _grade(blob: str) -> str | None:
    for grade in ("lead", "senior", "middle", "junior", "intern"):
        if grade in blob:
            return grade
    if "ведущ" in blob or "principal" in blob or "head " in blob or "тимлид" in blob or "tech lead" in blob:
        return "lead"
    if "старш" in blob or "staff" in blob:
        return "senior"
    if "средн" in blob:
        return "middle"
    if "младш" in blob:
        return "junior"
    if "стажёр" in blob or "стажер" in blob:
        return "intern"
    return None


def _format(job: dict, blob: str) -> str | None:
    if job.get("remote") or any(word in blob for word in _FORMAT_WORDS["remote"]):
        return "remote"
    if any(word in blob for word in _FORMAT_WORDS["hybrid"]):
        return "hybrid"
    if any(word in blob for word in _FORMAT_WORDS["office"]):
        return "office"
    return None


def _stack_hit(item: str, blob: str) -> bool:
    return stack_hits(item, blob)


def career_job_matches(job: dict, params: dict | None) -> bool:
    data = normalize_career_params(params)
    if is_non_it_title(str(job.get("title") or "")):
        return False
    blob = _blob(job)
    search = str(data.get("search") or "").strip().lower()
    if search:
        tokens = [token for token in search.replace(",", " ").split() if token]
        if any(token not in blob for token in tokens):
            return False
    stack = data.get("stack") or []
    if stack and not _stack_is_wide(stack):
        if not any(_stack_hit(item, blob) for item in stack):
            return False
    elif _stack_is_wide(stack) or not stack:
        if not looks_like_it_job(job):
            return False
    levels = data.get("levels") or []
    if levels:
        grade = _grade(blob)
        if grade and grade not in levels and not (grade == "lead" and "head" in levels):
            return False
    formats = data.get("formats") or []
    if formats:
        found = _format(job, blob)
        if found and found not in formats:
            return False
    cities = data.get("cities") or []
    if cities and "113" not in cities:
        location = str(job.get("location") or "")
        remote = bool(job.get("remote")) or _format(job, blob) == "remote"
        if not remote or "remote" not in formats:
            if location and not location_hits_cities(location, cities):
                return False
    if data.get("only_salary") or data.get("salary_from"):
        raw = job.get("salary_raw") or job.get("salary")
        minimum, maximum, _currency = parse_salary(raw if isinstance(raw, str) else None)
        amount = minimum or maximum
        if data.get("only_salary") and not amount:
            return False
        need = int(data.get("salary_from") or 0)
        if need and amount and amount < need:
            return False
    return True
