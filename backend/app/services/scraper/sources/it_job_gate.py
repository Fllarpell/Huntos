"""Drop sales / support / HR / game-art titles that boards dump into «IT»."""

from __future__ import annotations

from app.services.scraper.sources.stack_lexicon import fold_text, matching_stack_ids

# Substrings against fold_text(title). Keep specific: bare «менеджер» is Product Manager.
JUNK_TITLE_NEEDLES: tuple[str, ...] = (
    "менеджер по продаж",
    "менеджер продаж",
    "sales manager",
    "account manager",
    "специалист по продаж",
    "менеджер по работе с клиент",
    "подбор персонал",
    "рекрутер",
    "recruiter",
    "сорсер",
    "sourcer",
    "hr bp",
    "hr-менеджер",
    "hr менеджер",
    "менеджер по персонал",
    "специалист по кадрам",
    "технической поддерж",
    "техническая поддерж",
    "технической поддержки",
    "technical support",
    "tech support",
    "helpdesk",
    "help desk",
    "специалист поддержки",
    "поддержки клиент",
    "поддержка клиент",
    "customer support",
    "оператор торгов",
    "оператор call",
    "оператор колл",
    "оператор пк",
    "minecraft",
    "майнкрафт",
    "аниматор",
    "графический дизайнер",
    "graphic designer",
    "иллюстратор",
    "2d-художник",
    "2d художник",
    "3d-художник",
    "3d художник",
    "контент-менеджер",
    "контент менеджер",
    "smm-менеджер",
    "smm менеджер",
    "таргетолог",
    "менеджер маркетплейс",
    "продавец",
    "кассир",
    "курьер",
    "водитель",
    "бухгалтер",
    "юрист",
    "секретар",
    "офис-менеджер",
    "офис менеджер",
)

_IT_TITLE_NEEDLES: tuple[str, ...] = (
    "разработчик",
    "разработк",
    "developer",
    "engineer",
    "инженер",
    "программист",
    "programmer",
    "backend",
    "frontend",
    "fullstack",
    "full stack",
    "devops",
    "sre",
    "тестировщик",
    "тестирован",
    "data scientist",
    "data engineer",
    "machine learning",
    "аналитик",
    "analyst",
    "архитектор",
    "architect",
    "системный админ",
    "системный аналитик",
    "ios",
    "android",
    "product manager",
    "продакт",
    "product owner",
    "ux/ui",
    "ux-ui",
    "продуктовый дизайнер",
)


JUNK_TITLE_PAIRS: tuple[tuple[str, str], ...] = (
    ("подбор", "персонал"),
    ("техническ", "поддерж"),
    ("поддерж", "клиент"),
)


def is_non_it_title(title: str | None) -> bool:
    folded = fold_text(title or "")
    if not folded:
        return False
    if any(needle in folded for needle in JUNK_TITLE_NEEDLES):
        return True
    return any(left in folded and right in folded for left, right in JUNK_TITLE_PAIRS)


def listing_is_it_job(job: dict | None) -> bool:
    title = str((job or {}).get("title") or "")
    return not is_non_it_title(title)


def looks_like_it_job(job: dict | None) -> bool:
    """Wide hunt: not junk, and a stack hit or an engineering-ish title."""
    job = job or {}
    title = str(job.get("title") or "")
    if is_non_it_title(title):
        return False
    skills = job.get("skills") or []
    if matching_stack_ids(title, skills, str(job.get("category") or "")):
        return True
    folded = fold_text(title)
    return any(needle in folded for needle in _IT_TITLE_NEEDLES)
