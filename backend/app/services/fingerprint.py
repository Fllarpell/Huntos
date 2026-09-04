from __future__ import annotations

import re
import unicodedata

from app.services.company_icon import icon_brand_key
from app.services.scraper.sources.stack_lexicon import matching_stack_ids

_NOISE = re.compile(r"[^a-zа-я0-9]+", re.IGNORECASE)
_ANON = {"", "nda", "confidential", "компания не указана", "без компании", "hidden"}
_GRADE = {
    "intern",
    "junior",
    "middle",
    "senior",
    "lead",
    "head",
    "principal",
    "staff",
    "interns",
    "стажер",
    "стажера",
    "младший",
    "старший",
    "ведущий",
    "главный",
    "тимлид",
    "техлид",
}
_FORMAT = {
    "удаленно",
    "удаленка",
    "remote",
    "hybrid",
    "гибрид",
    "гибридный",
    "офис",
    "office",
    "fulltime",
    "фултайм",
}
_FILLER = {
    "вакансия",
    "vacancy",
    "job",
    "required",
    "ищем",
    "требуется",
    "в",
    "на",
    "по",
    "для",
    "and",
    "or",
}
_ROLE_ALIASES = {
    "разработчик": "dev",
    "developer": "dev",
    "engineer": "dev",
    "инженер": "dev",
    "программист": "dev",
    "programmer": "dev",
    "golang": "go",
    "фронтенд": "frontend",
    "фронт": "frontend",
    "бэкенд": "backend",
    "бекенд": "backend",
    "фулстек": "fullstack",
    "фуллстек": "fullstack",
}
_COMPOUNDS = {
    ("front", "end"): "frontend",
    ("back", "end"): "backend",
    ("full", "stack"): "fullstack",
    ("node", "js"): "nodejs",
    ("machine", "learning"): "ml",
}
_LANG_STACKS = frozenset(
    {"python", "go", "java", "csharp", "cpp", "php", "rust", "kotlin", "scala", "ruby", "nodejs", "onec"}
)
_SIDE_STACKS = frozenset(
    {
        "frontend",
        "backend",
        "fullstack",
        "mobile",
        "android",
        "ios",
        "qa",
        "devops",
        "sre",
        "security",
        "ml",
        "data",
        "embedded",
        "analytics",
        "sysanalyst",
        "product",
        "design",
    }
)
_DISTINCT_STACKS = _LANG_STACKS | (_SIDE_STACKS - {"backend", "fullstack"})


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower().replace("ё", "е")
    text = _NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _city_tokens() -> frozenset[str]:
    from app.services.scraper.sources.geo import CITIES

    tokens: set[str] = set()
    for city in CITIES:
        if city.hh_id == "113":
            continue
        for word in (city.label, *city.words):
            for part in _norm(word).split():
                if len(part) >= 4:
                    tokens.add(part)
    return frozenset(tokens)


_CITY_TOKENS: frozenset[str] | None = None


def _cities() -> frozenset[str]:
    global _CITY_TOKENS
    if _CITY_TOKENS is None:
        _CITY_TOKENS = _city_tokens()
    return _CITY_TOKENS


def company_key(company: str | None) -> str:
    brand = icon_brand_key(company)
    if brand:
        return brand
    name = _norm(company)
    if name in _ANON:
        return "nda"
    return name[:40]


def _alias_tokens(tokens: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(tokens):
        pair = (tokens[index], tokens[index + 1]) if index + 1 < len(tokens) else None
        if pair in _COMPOUNDS:
            merged.append(_COMPOUNDS[pair])
            index += 2
            continue
        merged.append(_ROLE_ALIASES.get(tokens[index], tokens[index]))
        index += 1
    return merged


def title_key(title: str | None, company: str | None = None) -> str:
    dropped = _GRADE | _FORMAT | _FILLER | _cities()
    company_bits = set(_norm(company).split()) if company else set()
    kept: list[str] = []
    seen: set[str] = set()
    for token in _alias_tokens(_norm(title).split()):
        if len(token) < 2 or token in dropped or token in company_bits:
            continue
        if token in seen:
            continue
        seen.add(token)
        kept.append(token)
    kept.sort()
    return " ".join(kept)[:80]


def vacancy_fingerprint(title: str | None, company: str | None) -> str:
    return f"{company_key(company)}|{title_key(title, company)}"[:190]


def stacks_conflict(left: list[str] | tuple[str, ...] | None, right: list[str] | tuple[str, ...] | None) -> bool:
    a = {str(item) for item in (left or [])}
    b = {str(item) for item in (right or [])}
    lang_a, lang_b = a & _LANG_STACKS, b & _LANG_STACKS
    if lang_a and lang_b and not (lang_a & lang_b):
        return True
    side_a, side_b = a & _SIDE_STACKS, b & _SIDE_STACKS
    if "fullstack" in a or "fullstack" in b:
        side_a -= {"frontend", "backend", "fullstack"}
        side_b -= {"frontend", "backend", "fullstack"}
    if side_a and side_b and not (side_a & side_b):
        return True
    return False


def fingerprints_close(
    left: str | None,
    right: str | None,
    left_stacks: list[str] | tuple[str, ...] | None = None,
    right_stacks: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Same company brand and overlapping role — HH vs career board, not Go vs Python."""
    if not left or not right or "|" not in left or "|" not in right:
        return False
    left_co, left_title = left.split("|", 1)
    right_co, right_title = right.split("|", 1)
    if not left_co or left_co != right_co or left_co == "nda":
        return False
    a = {part for part in left_title.split() if part}
    b = {part for part in right_title.split() if part}
    if not a or not b:
        return False
    stacks_a = list(left_stacks) if left_stacks is not None else matching_stack_ids(left_title)
    stacks_b = list(right_stacks) if right_stacks is not None else matching_stack_ids(right_title)
    if stacks_conflict(stacks_a, stacks_b):
        return False
    overlap = len(a & b)
    if overlap >= 2 and overlap / len(a | b) >= 0.5:
        return True
    distinctive = set(stacks_a) & set(stacks_b) & _DISTINCT_STACKS
    return bool(distinctive) and overlap >= 1
