"""Salary corridor stats from open forks (salary_min)."""

from __future__ import annotations

from collections import Counter, defaultdict

from app.services.scraper.sources.stack_lexicon import STACK_IDS, fold_text, matching_stack_ids

OPEN_SOURCES = frozenset({"habr", "getmatch"})
CORRIDOR_MIN_N = 3

GRADE_ORDER = ("intern", "junior", "middle", "senior", "lead", "head")
GRADE_ALIASES = {
    "intern": "intern",
    "internship": "intern",
    "стажер": "intern",
    "стажёр": "intern",
    "junior": "junior",
    "jr": "junior",
    "джун": "junior",
    "джуниор": "junior",
    "middle": "middle",
    "mid": "middle",
    "мидл": "middle",
    "мидлл": "middle",
    "senior": "senior",
    "sr": "senior",
    "сеньор": "senior",
    "синьор": "senior",
    "lead": "lead",
    "teamlead": "lead",
    "team-lead": "lead",
    "тимлид": "lead",
    "techlead": "lead",
    "tech-lead": "lead",
    "техлид": "lead",
    "head": "head",
    "principal": "head",
    "staff": "head",
}

SPECIALTY_LABELS = {
    "python": "Python",
    "go": "Go",
    "java": "Java",
    "csharp": ".NET/C#",
    "cpp": "C++",
    "php": "PHP",
    "rust": "Rust",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "ruby": "Ruby",
    "nodejs": "Node.js",
    "onec": "1C",
    "backend": "Backend",
    "frontend": "Frontend",
    "fullstack": "Fullstack",
    "mobile": "Mobile",
    "android": "Android",
    "ios": "iOS",
    "devops": "DevOps",
    "qa": "QA",
    "ml_ai": "ML/AI",
    "data_engineer": "Data Engineer",
    "analytics": "Аналитика",
    "design": "Дизайн",
    "management": "Менеджмент",
    "unknown": "без специальности",
}


def percentile(values: list[int], p: float) -> int | None:
    """Linear interpolation percentile; p in 0..100."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    frac = rank - low
    return int(round(ordered[low] + (ordered[high] - ordered[low]) * frac))


def median(values: list[int]) -> int | None:
    return percentile(values, 50)


def normalize_grade(raw: object) -> str:
    text = fold_text(str(raw or "").strip())
    if not text:
        return "unknown"
    if text in GRADE_ALIASES:
        return GRADE_ALIASES[text]
    for key, canon in GRADE_ALIASES.items():
        if key in text:
            return canon
    return "unknown"


def specialty_of(row: object) -> str:
    skills = getattr(row, "skills", None) or []
    title = getattr(row, "title", None) or ""
    category = getattr(row, "category", None) or ""
    for skill in skills:
        key = fold_text(str(skill))
        if key in STACK_IDS:
            return key
    hits = matching_stack_ids(title, " ".join(str(item) for item in skills), category)
    if hits:
        return hits[0]
    cat = fold_text(str(category))
    if cat in STACK_IDS or cat in SPECIALTY_LABELS:
        return cat
    return "unknown"


def salary_corridor(
    values: list[int],
    *,
    currency: str = "RUB",
    open_n: int | None = None,
    by_source: dict[str, int] | None = None,
    key: str | None = None,
    label: str | None = None,
) -> dict:
    """p25 / median / p75 over lower bounds of open salary forks."""
    n = len(values)
    sources = {src: count for src, count in (by_source or {}).items() if count > 0}
    out = {
        "n": n,
        "p25": percentile(values, 25) if n else None,
        "median": median(values) if n else None,
        "p75": percentile(values, 75) if n else None,
        "currency": currency,
        "open_share": round(open_n / n, 2) if n and open_n is not None else None,
        "by_source": sources,
    }
    if key is not None:
        out["key"] = key
    if label is not None:
        out["label"] = label
    return out


def _bucket_corridor(
    buckets: dict[str, list[tuple[int, str]]],
    *,
    labels: dict[str, str],
    order: tuple[str, ...] | None = None,
    currency: str = "RUB",
) -> list[dict]:
    keys = list(order) if order else []
    keys.extend(sorted(k for k in buckets if k not in keys and k != "unknown"))
    if "unknown" in buckets:
        keys.append("unknown")
    out: list[dict] = []
    for key in keys:
        items = buckets.get(key) or []
        if not items:
            continue
        amounts = [amount for amount, _ in items]
        sources: Counter[str] = Counter(source for _, source in items)
        open_n = sum(1 for _, source in items if source in OPEN_SOURCES)
        out.append(
            salary_corridor(
                amounts,
                currency=currency,
                open_n=open_n,
                by_source=dict(sources),
                key=key,
                label=labels.get(key, key),
            )
        )
    return out


def filter_salary_rows(
    rows: list,
    *,
    grade: str | None = None,
    specialty: str | None = None,
) -> list:
    """Keep rows matching optional grade / specialty keys."""
    raw_grade = (grade or "").strip().lower()
    want_grade = None if raw_grade in {"", "all", "any"} else normalize_grade(raw_grade)
    raw_specialty = (specialty or "").strip().lower()
    want_specialty = None if raw_specialty in {"", "all", "any"} else raw_specialty
    if want_grade is None and want_specialty is None:
        return list(rows)
    out: list = []
    for row in rows:
        if want_grade is not None and normalize_grade(getattr(row, "grade", None)) != want_grade:
            continue
        if want_specialty is not None and specialty_of(row) != want_specialty:
            continue
        out.append(row)
    return out


def filter_options(corridor: dict, *, min_n: int = CORRIDOR_MIN_N) -> dict[str, list[dict]]:
    """Dropdown options: only slices with enough forks. No 'мало данных' stubs."""

    def _opts(items: list | None) -> list[dict]:
        rows = []
        for item in items or []:
            if int(item.get("n") or 0) < min_n:
                continue
            rows.append(
                {
                    "key": item.get("key"),
                    "label": item.get("label") or item.get("key"),
                    "n": item.get("n"),
                    "p25": item.get("p25"),
                    "median": item.get("median"),
                    "p75": item.get("p75"),
                }
            )
        return rows

    return {
        "grades": _opts(corridor.get("by_grade")),
        "specialties": _opts(corridor.get("by_specialty")),
    }


def corridor_from_vacancies(
    rows: list,
    *,
    currency: str = "RUB",
    grade: str | None = None,
    specialty: str | None = None,
    aggregators: list[dict] | None = None,
) -> dict:
    """Collect RUB salary_min values and build overall + by_grade + by_specialty.

    ``aggregators`` are survey/profession snapshots (Habr, GetMatch, hh.ru career, Levels).
    They enter the same p25/median/p75 mix, weighted, without replacing vacancy n.
    """
    scoped = filter_salary_rows(rows, grade=grade, specialty=specialty)
    amounts: list[int] = []
    open_n = 0
    counts: Counter[str] = Counter()
    by_grade: dict[str, list[tuple[int, str]]] = defaultdict(list)
    by_specialty: dict[str, list[tuple[int, str]]] = defaultdict(list)
    vacancy_n = 0

    for row in scoped:
        amount = getattr(row, "salary_min", None)
        if amount is None:
            continue
        try:
            value = int(amount)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        cur = (getattr(row, "salary_currency", None) or "RUB").strip().upper()
        if cur and cur not in {"RUB", "RUR", "₽"}:
            continue
        source = (getattr(row, "source", None) or "").strip().lower() or "other"
        amounts.append(value)
        vacancy_n += 1
        counts[source] += 1
        if source in OPEN_SOURCES:
            open_n += 1
        g = normalize_grade(getattr(row, "grade", None))
        by_grade[g].append((value, source))
        by_specialty[specialty_of(row)].append((value, source))

    from app.services.salary_aggregators import (
        AGGREGATOR_WEIGHT,
        aggregator_points,
        expand_aggregator_observations,
        filter_aggregators,
    )

    matched = filter_aggregators(aggregators, grade=grade, specialty=specialty)
    for amount, source, _agg_grade, _agg_specialty in expand_aggregator_observations(matched):
        amounts.append(amount)
    for row in matched:
        counts[str(row.get("source") or "aggregator")] += 1

    raw_grade = (grade or "").strip().lower()
    want_grade = None if raw_grade in {"", "all", "any"} else normalize_grade(raw_grade)
    raw_specialty = (specialty or "").strip().lower()
    want_specialty = None if raw_specialty in {"", "all", "any"} else raw_specialty
    seen_bucket_keys: set[tuple] = set()
    for row in aggregators or []:
        if row.get("mix") is False:
            continue
        source = str(row.get("source") or "aggregator")
        points = aggregator_points(row)
        if not points:
            continue
        row_grade = row.get("grade") or None
        if row_grade:
            row_grade = normalize_grade(row_grade)
            if row_grade == "unknown":
                row_grade = None
        row_specialty = (row.get("specialty") or "").strip() or None
        # Grade-only slices (Habr Junior) fill by_grade even when not in the overall mix.
        if row_grade and (want_grade is None or row_grade == want_grade) and (
            want_specialty is None or row_specialty == want_specialty
        ):
            key = ("grade", row_grade, source, row.get("key"))
            if key not in seen_bucket_keys:
                seen_bucket_keys.add(key)
                for amount in points:
                    for _ in range(AGGREGATOR_WEIGHT):
                        by_grade[row_grade].append((amount, source))
        if row_specialty and (want_specialty is None or row_specialty == want_specialty) and (
            want_grade is None or row_grade == want_grade
        ):
            key = ("spec", row_specialty, source, row.get("key"))
            if key not in seen_bucket_keys:
                seen_bucket_keys.add(key)
                for amount in points:
                    for _ in range(AGGREGATOR_WEIGHT):
                        by_specialty[row_specialty].append((amount, source))

    grade_labels = {key: key for key in GRADE_ORDER}
    grade_labels["unknown"] = "без грейда"
    overall = salary_corridor(amounts, currency=currency, open_n=open_n, by_source=dict(counts))
    overall["n"] = vacancy_n + len(matched)
    overall["n_vacancies"] = vacancy_n
    overall["n_aggregators"] = len(matched)
    overall["open_share"] = round(open_n / vacancy_n, 2) if vacancy_n else None
    overall["by_grade"] = _bucket_corridor(by_grade, labels=grade_labels, order=GRADE_ORDER, currency=currency)
    overall["by_specialty"] = _bucket_corridor(
        by_specialty,
        labels=SPECIALTY_LABELS,
        currency=currency,
    )
    overall["grade"] = grade if grade and grade not in {"", "all", "any"} else None
    overall["specialty"] = specialty if specialty and specialty not in {"", "all", "any"} else None
    return overall
