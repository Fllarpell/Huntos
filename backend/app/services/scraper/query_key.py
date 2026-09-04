from __future__ import annotations

import hashlib
import json

from app.services.scraper.registry import get_spec
from app.services.scraper.sources.hirehi_filters import normalize_hirehi_params
from app.services.scraper.sources.stack_lexicon import parse_inbox_query

# Stack chips that this donor can encode. Unmapped tokens stay in `search`.
_HIREHI_STACK = {
    "python": "python",
    "go": "go",
    "java": "java",
    "backend": "backend",
    "frontend": "frontend",
    "fullstack": "fullstack",
    "nodejs": "nodejs",
    "mobile": "mobile",
    "android": "android",
    "ios": "ios",
    "ml": "ml_ai",
    "data": "data_engineer",
    "csharp": "netc",
    "cpp": "cpp",
    "php": "php",
    "rust": "rust",
    "kotlin": "kotlin",
    "onec": "onec",
}
_GETMATCH_STACK = {
    "python": "python",
    "go": "golang",
    "java": "java_scala",
    "scala": "java_scala",
    "frontend": "js_frontend",
    "nodejs": "js_backend",
    "fullstack": "fullstack",
    "qa": "qa_auto",
    "devops": "dev_ops",
    "sre": "dev_ops",
    "ml": "data_science",
    "android": "android",
    "ios": "ios",
    "csharp": "c_sharp",
    "php": "php",
    "kotlin": "kotlin",
    "sysanalyst": "system_analyst",
    "product": "product_management",
}
_HABR_STACK = {
    "backend": "2",
    "frontend": "3",
    "fullstack": "4",
    "mobile": "5",
    "android": "5",
    "ios": "5",
    "qa": "10",
    "devops": "22",
    "sre": "22",
    "ml": "44",
    "data": "76",
    "analytics": "43",
    "sysanalyst": "41",
    "architect": "73",
    "embedded": "7",
}


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def fold_search_stacks(source: str, params: dict | None) -> dict:
    """«go» / «golang» in the search box is the same hunt as the Go chip."""
    data = dict(params or {})
    search = str(data.get("search") or data.get("text") or data.get("q") or "").strip()
    if not search:
        return data
    stacks, leftover, _topics = parse_inbox_query(search)
    if not stacks:
        return data
    mapped: list[str] = []
    leftover_bits = [leftover] if leftover.strip() else []
    for item in stacks:
        if source == "hirehi" and item in _HIREHI_STACK:
            mapped.append(item)
        elif source == "getmatch" and item in _GETMATCH_STACK:
            mapped.append(item)
        elif source == "habr" and item in _HABR_STACK:
            mapped.append(item)
        elif source in {"hh", "geekjob", "career"}:
            mapped.append(item)
        else:
            leftover_bits.append(item)
    if not mapped:
        return data
    folded = " ".join(bit for bit in leftover_bits if bit).strip()
    data["search"] = folded
    if "text" in data:
        data["text"] = folded
    if "q" in data:
        data["q"] = folded
    stack = _as_list(data.get("stack"))
    for item in mapped:
        if item not in stack:
            stack.append(item)
    data["stack"] = stack
    if source == "hirehi":
        subs = _as_list(data.get("subcategory"))
        for item in mapped:
            slug = _HIREHI_STACK.get(item, item)
            if slug not in subs:
                subs.append(slug)
        data["subcategory"] = subs
    elif source == "getmatch":
        specs = _as_list(data.get("specialties") or data.get("specialty"))
        for item in mapped:
            slug = _GETMATCH_STACK.get(item)
            if slug and slug not in specs:
                specs.append(slug)
        if specs:
            data["specialties"] = specs
    elif source == "habr":
        specs = _as_list(data.get("s") or data.get("specializations"))
        for item in mapped:
            slug = _HABR_STACK.get(item)
            if slug and slug not in specs:
                specs.append(slug)
        if specs:
            data["s"] = specs
    return data


def canonical_params(source: str, params: dict | None) -> dict:
    """Identity of a shared crawl. Sort/headed don't get their own donor trip."""
    folded = fold_search_stacks(source, params)
    spec = get_spec(source)
    if spec is None:
        data = normalize_hirehi_params(folded)
        data.pop("sort", None)
        data["search"] = (data.get("search") or "").strip().casefold()
        return data
    data = spec.normalize_params(folded)
    for key in spec.identity_drop:
        data.pop(key, None)
    if "search" in data and isinstance(data["search"], str):
        data["search"] = data["search"].strip().casefold()
    return data


def fetch_params(source: str, params: dict | None) -> dict:
    """What the host actually sends to the donor for a shared key."""
    spec = get_spec(source)
    data = canonical_params(source, params)
    if spec is None:
        data["sort"] = "date"
        return data
    data.update(spec.fetch_defaults)
    if source == "hh":
        data["headed"] = bool((params or {}).get("headed"))
    return data


def crawl_label(source: str, params: dict | None) -> str:
    spec = get_spec(source)
    data = fetch_params(source, params)
    if spec is None:
        return source
    return spec.auto_name(data)


def make_query_key(source: str, params: dict | None) -> str:
    body = json.dumps(
        canonical_params(source, params),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{source}:{body}".encode()).hexdigest()[:40]
