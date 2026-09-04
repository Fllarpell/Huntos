"""Normalize salary-aggregator snapshots and expand them into corridor observations."""

from __future__ import annotations

from app.services.salary_stats import normalize_grade

# Copies of each percentile so aggregators actually move the vacancy mix
# without drowning it (Habr n=40k would otherwise replace the sample).
AGGREGATOR_WEIGHT = 16


def levels_as_aggregators(items: list[dict] | None) -> list[dict]:
    rows: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        monthly = item.get("monthly") if isinstance(item.get("monthly"), dict) else {}
        key = str(item.get("key") or "")
        rows.append(
            {
                "key": key or "levels",
                "grade": None,
                "specialty": None,
                "label": item.get("label") or "Software Engineer",
                "n": None,
                "p25": monthly.get("p25"),
                "median": monthly.get("median"),
                "p75": monthly.get("p75"),
                "currency": "RUB",
                "period": "month",
                "source": "levels.fyi",
                "url": item.get("url"),
                "attribution": item.get("attribution") or "Levels.fyi",
                "note": item.get("note"),
                # Russia overall is the mix prior; Moscow is display-only (same SWE slice).
                "mix": key == "swe_russia",
            }
        )
    return rows


def aggregator_points(row: dict) -> list[int]:
    values: list[int] = []
    for key in ("p25", "median", "p75", "p90"):
        raw = row.get(key)
        if raw is None:
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in values:
            values.append(number)
    return values


def aggregator_matches(row: dict, *, grade: str | None, specialty: str | None) -> bool:
    """Grade/specialty slices use matching aggregator rows; overall keeps market priors."""
    if row.get("mix") is False:
        return False
    raw_grade = (grade or "").strip().lower()
    want_grade = None if raw_grade in {"", "all", "any"} else normalize_grade(raw_grade)
    want_specialty = (specialty or "").strip().lower()
    if want_specialty in {"", "all", "any"}:
        want_specialty = None
    row_grade = row.get("grade") or None
    if row_grade:
        row_grade = normalize_grade(row_grade)
        if row_grade == "unknown":
            row_grade = None
    row_specialty = (row.get("specialty") or "").strip().lower() or None

    if want_grade:
        if row_grade != want_grade:
            return False
    elif row_grade and not row_specialty:
        # Unfiltered overall: skip Intern/Junior/... slices (they have their own buckets).
        return False

    if want_specialty:
        if row_specialty != want_specialty:
            return False
    return True


def filter_aggregators(
    rows: list[dict] | None,
    *,
    grade: str | None = None,
    specialty: str | None = None,
) -> list[dict]:
    return [row for row in (rows or []) if aggregator_matches(row, grade=grade, specialty=specialty)]


def expand_aggregator_observations(
    rows: list[dict],
    *,
    weight: int = AGGREGATOR_WEIGHT,
) -> list[tuple[int, str, str | None, str | None]]:
    """(amount, source, grade, specialty) repeated `weight` times per percentile."""
    copies = max(1, int(weight))
    out: list[tuple[int, str, str | None, str | None]] = []
    for row in rows:
        points = aggregator_points(row)
        if not points:
            continue
        source = str(row.get("source") or "aggregator").strip() or "aggregator"
        grade = row.get("grade") or None
        specialty = (row.get("specialty") or "").strip() or None
        for amount in points:
            for _ in range(copies):
                out.append((amount, source, grade, specialty))
    return out
