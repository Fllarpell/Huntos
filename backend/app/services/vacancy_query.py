from __future__ import annotations

from sqlalchemy import Select, String, and_, cast, not_, or_, select
from sqlalchemy.sql import ColumnElement

from app.models.scraper_config import ScraperConfig
from app.models.vacancy import Vacancy
from app.models.vacancy_search import VacancySearch
from app.services.scraper.sources.it_job_gate import JUNK_TITLE_NEEDLES, JUNK_TITLE_PAIRS
from app.services.scraper.sources.stack_lexicon import (
    STACK_IDS,
    content_matches_stack,
    fold_text,
    parse_inbox_query,
    stack_evidence_terms,
)
from app.services.search_text import fold_expr


def _content_like_bits(like: str) -> list[ColumnElement]:
    """Title / skills / tags / category — not search-config names, not whole CRM."""
    return [
        fold_expr(Vacancy.title).like(like),
        fold_expr(Vacancy.category).like(like),
        cast(Vacancy.skills, String).like(like),
        cast(Vacancy.tags, String).like(like),
    ]


def _content_like_bits_broad(like: str) -> list[ColumnElement]:
    return [
        *_content_like_bits(like),
        fold_expr(Vacancy.company).like(like),
        fold_expr(Vacancy.description).like(like),
        fold_expr(Vacancy.requirements).like(like),
    ]


_LANGUAGE_STACKS = frozenset(
    {
        "python",
        "go",
        "java",
        "csharp",
        "cpp",
        "php",
        "rust",
        "kotlin",
        "scala",
        "ruby",
        "nodejs",
        "onec",
    }
)

_ROLE_TITLE_HINTS = (
    "%разработ%",
    "%developer%",
    "%программист%",
    "%backend%",
    "%бэкенд%",
    "%бекенд%",
    "%software%",
)


def _title_role_hint() -> ColumnElement:
    return or_(*(fold_expr(Vacancy.title).like(hint) for hint in _ROLE_TITLE_HINTS))


def _skills_tags_like(syn: str) -> list[ColumnElement]:
    """Case-insensitive skills/tags match. Prefer JSON chip quotes for short stems."""
    from sqlalchemy import func

    skills = func.lower(cast(Vacancy.skills, String))
    tags = func.lower(cast(Vacancy.tags, String))
    # Bare %java% hits javascript; chip quotes keep languages distinct.
    if len(syn) <= 4 or syn in {"java", "node", "rust", "ruby", "scala", "swift", "react", "vue"}:
        return [
            skills.like(f'%"{syn}"%'),
            skills.like(f"%'{syn}'%"),
            tags.like(f'%"{syn}"%'),
            tags.like(f"%'{syn}'%"),
        ]
    lowered = f"%{syn}%"
    return [skills.like(lowered), tags.like(lowered)]


def _title_bound_bits(syn: str) -> list[ColumnElement]:
    return [
        fold_expr(Vacancy.title).like(f"%{syn}-%"),
        fold_expr(Vacancy.title).like(f"%{syn} %"),
        fold_expr(Vacancy.title).like(f"{syn} %"),
        fold_expr(Vacancy.title).like(f"% {syn}"),
        fold_expr(Vacancy.title).like(f"% {syn})%"),
        fold_expr(Vacancy.title).like(f"%({syn})%"),
        fold_expr(Vacancy.title).like(f"%({syn} %"),
        fold_expr(Vacancy.title).like(f"%({syn},%"),
        fold_expr(Vacancy.category).like(f"%{syn}%"),
    ]


def stack_content_clause(stack_id: str) -> ColumnElement | None:
    """Vacancy text must support this stack (lexicon), not only polluted stack_ids."""
    from app.services.scraper.sources.stack_lexicon import _AMBIGUOUS_EVIDENCE, _TOKENS

    terms = stack_evidence_terms(stack_id)
    title_bits: list[ColumnElement] = []
    for syn in terms:
        like = f"%{syn}%"
        title_bits.extend(
            [
                fold_expr(Vacancy.title).like(like),
                fold_expr(Vacancy.category).like(like),
            ]
        )

    shorts = {
        fold_text(stack_id),
        *(fold_text(item) for item in _TOKENS.get(stack_id, ())),
    }
    skill_bits: list[ColumnElement] = []
    for syn in shorts:
        if len(syn) < 2:
            continue
        # Bound forms in title always count.
        if syn in _AMBIGUOUS_EVIDENCE or len(syn) < 4:
            title_bits.extend(_title_bound_bits(syn))
        if syn == "java":
            title_bits.append(
                and_(
                    fold_expr(Vacancy.title).like("%java%"),
                    ~fold_expr(Vacancy.title).like("%javascript%"),
                    ~fold_expr(Vacancy.title).like("%typescript%"),
                )
            )
        # Exact skill chips: for languages require a role-ish title so laundry-list
        # ML skills («…, java, …») do not pass a java search.
        chip = or_(*_skills_tags_like(syn))
        if stack_id in _LANGUAGE_STACKS:
            skill_bits.append(and_(chip, _title_role_hint()))
        else:
            skill_bits.append(chip)

    parts = [or_(*title_bits)] if title_bits else []
    if skill_bits:
        parts.append(or_(*skill_bits))
    if not parts:
        return None
    return or_(*parts)


def stack_ids_clause(ids: list[str], *, require_content: bool = True) -> ColumnElement | None:
    """OR across stacks. Each stack needs JSON chip and (by default) text evidence."""
    wanted = [item for item in ids if item in STACK_IDS]
    if not wanted:
        return None
    per_stack: list[ColumnElement] = []
    for item in wanted:
        chip = cast(Vacancy.stack_ids, String).like(f'%"{item}"%')
        if not require_content:
            per_stack.append(chip)
            continue
        evidence = stack_content_clause(item)
        if evidence is None:
            per_stack.append(chip)
        else:
            # Content lexicon is source of truth; chip alone used to leak Java under «ml».
            # Keep chip OR content so correctly tagged cards without the synonym string still pass
            # *only if* content also matches via matching_stack_ids path — here we require content.
            per_stack.append(evidence)
    return or_(*per_stack)


def search_ids_clause(ids: list[int]) -> ColumnElement | None:
    if not ids:
        return None
    linked = select(VacancySearch.vacancy_id).where(VacancySearch.scraper_config_id.in_(ids))
    return or_(Vacancy.scraper_config_id.in_(ids), Vacancy.id.in_(linked))


def topic_match_clause(synonyms: list[str] | tuple[str, ...]) -> ColumnElement | None:
    """OR of synonym hits against vacancy content (not search-config names)."""
    bits: list[ColumnElement] = []
    seen: set[str] = set()
    for raw in synonyms:
        syn = fold_text(raw).strip()
        if len(syn) < 2 or syn in seen:
            continue
        seen.add(syn)
        like = f"%{syn}%"
        bits.extend(_content_like_bits_broad(like))
    if not bits:
        return None
    return or_(*bits)


def text_match_clause(q: str, *, user_id: int, include_searches: bool = True) -> ColumnElement:
    """Match leftover free text. Each whitespace token must hit (AND)."""
    tokens = [part for part in fold_text(q).split() if len(part) >= 2]
    if not tokens:
        tokens = [fold_text(q).strip()] if q.strip() else []
    token_clauses: list[ColumnElement] = []
    for raw in tokens:
        like = f"%{raw}%"
        alias_like = f"%{raw.lstrip('@')}%"
        bits: list[ColumnElement] = [
            *_content_like_bits_broad(like),
            func_coalesce_inn().like(alias_like),
            fold_expr(Vacancy.telegram_alias).like(alias_like),
            fold_expr(Vacancy.contact_email).like(like),
            func_coalesce_phone().like(like),
            fold_expr(Vacancy.source_url).like(like),
            Vacancy.source_id.like(alias_like),
            cast(Vacancy.extra_sources, String).like(like),
        ]
        if include_searches:
            named = (
                select(VacancySearch.vacancy_id)
                .join(ScraperConfig, ScraperConfig.id == VacancySearch.scraper_config_id)
                .where(ScraperConfig.user_id == user_id, fold_expr(ScraperConfig.name).like(like))
            )
            bits.append(Vacancy.id.in_(named))
            bits.append(
                Vacancy.scraper_config_id.in_(
                    select(ScraperConfig.id).where(
                        ScraperConfig.user_id == user_id,
                        fold_expr(ScraperConfig.name).like(like),
                    )
                )
            )
        token_clauses.append(or_(*bits))
    if len(token_clauses) == 1:
        return token_clauses[0]
    return and_(*token_clauses)


def func_coalesce_inn():
    from sqlalchemy import func

    return func.coalesce(Vacancy.company_inn, "")


def func_coalesce_phone():
    from sqlalchemy import func

    return func.coalesce(Vacancy.contact_phone, "")


def junk_title_clause() -> ColumnElement:
    likes = [fold_expr(Vacancy.title).like(f"%{needle}%") for needle in JUNK_TITLE_NEEDLES]
    pairs = [
        and_(
            fold_expr(Vacancy.title).like(f"%{left}%"),
            fold_expr(Vacancy.title).like(f"%{right}%"),
        )
        for left, right in JUNK_TITLE_PAIRS
    ]
    return or_(*likes, *pairs)


def apply_vacancy_query(
    stmt: Select,
    *,
    user_id: int,
    q: str | None = None,
    stack: list[str] | None = None,
    search_id: list[int] | None = None,
) -> Select:
    filters: list[ColumnElement] = []
    picked_stack = [item for item in (stack or []) if item in STACK_IDS]
    leftover = (q or "").strip()
    topics: list[tuple[str, ...]] = []
    if leftover:
        from_q, leftover, topics = parse_inbox_query(leftover)
        picked_stack = list(dict.fromkeys([*picked_stack, *from_q]))
    stack_filter = stack_ids_clause(picked_stack, require_content=True)
    if stack_filter is not None:
        filters.append(stack_filter)
    if topics:
        synonyms = [item for group in topics for item in group]
        topic_filter = topic_match_clause(synonyms)
        if topic_filter is not None:
            filters.append(topic_filter)
    if leftover:
        filters.append(text_match_clause(leftover, user_id=user_id))
    search_filter = search_ids_clause([int(item) for item in (search_id or [])])
    if search_filter is not None:
        filters.append(search_filter)
    filters.append(not_(junk_title_clause()))
    return stmt.where(*filters)


def _haystack(vacancy: Vacancy, *, search_names: list[str] | None = None) -> str:
    return (
        " ".join(
            str(part)
            for part in (
                vacancy.title,
                vacancy.company,
                vacancy.category,
                vacancy.description,
                vacancy.requirements,
                vacancy.telegram_alias,
                vacancy.contact_email,
                vacancy.contact_phone,
                vacancy.source_url,
                vacancy.source_id,
                *(vacancy.skills or []),
                *(vacancy.tags or []),
                *(search_names or []),
            )
            if part
        )
        .casefold()
        .replace("ё", "е")
    )


def vacancy_matches_query(vacancy: Vacancy, q: str, *, search_names: list[str] | None = None) -> bool:
    stacks, leftover, topics = parse_inbox_query(q)
    if stacks:
        blob_parts = (vacancy.title, vacancy.skills, vacancy.tags, vacancy.category)
        if not any(content_matches_stack(stack_id, *blob_parts) for stack_id in stacks):
            return False
    hay = _haystack(vacancy, search_names=search_names)
    if topics:
        synonyms = [fold_text(item) for group in topics for item in group]
        if not any(syn in hay for syn in synonyms if len(syn) >= 2):
            return False
    if leftover:
        for token in leftover.split():
            if token and token not in hay:
                return False
    return True
