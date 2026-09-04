"""Does a cached vacancy belong to this user's search — without another donor trip."""

from __future__ import annotations

from app.services.scraper.query_key import fold_search_stacks
from app.services.scraper.registry import get_spec
from app.services.scraper.sources.career_filters import _stack_is_wide, career_job_matches
from app.services.scraper.sources.geekjob_filters import geekjob_job_matches
from app.services.scraper.sources.it_job_gate import listing_is_it_job
from app.services.scraper.sources.stack_lexicon import stack_hits

_HIREHI_STACK = {
    "ml": "ml_ai",
    "data": "data_engineer",
    "csharp": "netc",
}


def match_params(source: str, params: dict | None) -> dict:
    data = fold_search_stacks(source, params)
    spec = get_spec(source)
    normalized = spec.normalize_params(data) if spec else dict(data)
    stack = [str(item) for item in (data.get("stack") or normalized.get("stack") or []) if item]
    if source == "hirehi" and not stack:
        raw = normalized.get("subcategory") or []
        stack = [str(item) for item in raw if item]
    if stack and "stack" not in normalized:
        normalized = {**normalized, "stack": stack}
    elif stack:
        normalized["stack"] = list(dict.fromkeys([*list(normalized.get("stack") or []), *stack]))
    return normalized


def listing_matches_params(payload: dict, source: str, params: dict | None) -> bool:
    if not listing_is_it_job(payload):
        return False
    if source == "career":
        return career_job_matches(payload, params)
    if source == "geekjob":
        return geekjob_job_matches(payload, params)
    data = match_params(source, params)
    blob = _blob(payload)
    search = str(data.get("search") or "").strip().casefold()
    if search:
        tokens = [token for token in search.replace(",", " ").split() if token]
        if any(token not in blob for token in tokens):
            return False
    stack = [str(item) for item in (data.get("stack") or []) if item]
    if source == "hirehi" and not stack:
        stack = [_HIREHI_STACK.get(str(item), str(item)) for item in (data.get("subcategory") or [])]
    if stack and not _stack_is_wide(stack):
        if not any(stack_hits(item, blob) for item in stack):
            return False
    return True


def _blob(payload: dict) -> str:
    skills = payload.get("skills") or []
    if isinstance(skills, str):
        skill_text = skills
    else:
        skill_text = " ".join(str(item) for item in skills)
    parts = [
        payload.get("title"),
        payload.get("company"),
        payload.get("specialty"),
        payload.get("requirements"),
        payload.get("description"),
        payload.get("tags"),
        skill_text,
    ]
    return " ".join(str(part) for part in parts if part).casefold()
