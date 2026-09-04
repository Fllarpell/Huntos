"""Official Levels.fyi markdown summaries (LLM .md routes) — no encrypted API scrape."""

from __future__ import annotations

import re
from dataclasses import dataclass

LEVELS_ORIGIN = "https://www.levels.fyi"
# Documented LLM-readable summaries: append .md to salary routes.
LEVELS_TARGETS = (
    {
        "key": "swe_russia",
        "label": "Software Engineer · Russia",
        "path": "/t/software-engineer/locations/russia.md",
        "html_path": "/t/software-engineer/locations/russia",
    },
    {
        "key": "swe_moscow",
        "label": "Software Engineer · Moscow",
        "path": "/t/software-engineer/locations/moscow-rus.md",
        "html_path": "/t/software-engineer/locations/moscow-rus",
    },
)

_MONEY = re.compile(
    r"RUB\s*([\d\s\u00a0\u202f.,]+)",
    re.I,
)
_MEDIAN = re.compile(
    r"Median Total Compensation:\s*RUB\s*([\d\s\u00a0\u202f.,]+)",
    re.I,
)
_P25_P75 = re.compile(
    r"25th\s*/\s*75th Percentile:\s*RUB\s*([\d\s\u00a0\u202f.,]+)\s*/\s*RUB\s*([\d\s\u00a0\u202f.,]+)",
    re.I,
)
_RANGE = re.compile(
    r"salary range.*?RUB\s*([\d\s\u00a0\u202f.,]+)\s*to\s*RUB\s*([\d\s\u00a0\u202f.,]+)",
    re.I | re.S,
)


def _parse_money(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


@dataclass
class LevelsBenchmark:
    key: str
    label: str
    url: str
    md_url: str
    currency: str
    period: str  # year
    p25: int | None
    median: int | None
    p75: int | None

    def as_monthly(self) -> dict:
        """Vacancy forks are monthly; Levels TC is annual — convert for side-by-side."""

        def month(value: int | None) -> int | None:
            if value is None:
                return None
            return int(round(value / 12))

        return {
            "n": None,
            "p25": month(self.p25),
            "median": month(self.median),
            "p75": month(self.p75),
            "currency": self.currency,
            "period": "month",
            "derived_from": "year_tc",
        }

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "url": self.url,
            "md_url": self.md_url,
            "source": "levels.fyi",
            "attribution": "Data source: Levels.fyi (https://www.levels.fyi)",
            "currency": self.currency,
            "period": self.period,
            "unit": "total_compensation",
            "note": "Годовой total compensation (base+stock+bonus). Месячный ряд — /12 для сравнения с вилками вакансий.",
            "annual": {
                "p25": self.p25,
                "median": self.median,
                "p75": self.p75,
            },
            "monthly": self.as_monthly(),
        }


def parse_levels_md(text: str, *, key: str, label: str, html_path: str, md_path: str) -> LevelsBenchmark | None:
    blob = text or ""
    median = None
    p25 = None
    p75 = None
    m = _MEDIAN.search(blob)
    if m:
        median = _parse_money(m.group(1))
    m = _P25_P75.search(blob)
    if m:
        p25 = _parse_money(m.group(1))
        p75 = _parse_money(m.group(2))
    if p25 is None or p75 is None:
        m = _RANGE.search(blob)
        if m:
            p25 = p25 or _parse_money(m.group(1))
            p75 = p75 or _parse_money(m.group(2))
    if median is None and p25 is not None and p75 is not None:
        median = int(round((p25 + p75) / 2))
    if median is None and p25 is None and p75 is None:
        return None
    return LevelsBenchmark(
        key=key,
        label=label,
        url=f"{LEVELS_ORIGIN}{html_path}",
        md_url=f"{LEVELS_ORIGIN}{md_path}",
        currency="RUB",
        period="year",
        p25=p25,
        median=median,
        p75=p75,
    )


async def fetch_levels_benchmarks(http=None) -> tuple[list[dict], list[str]]:
    """Fetch official .md summaries. Attribution required by Levels.fyi."""
    from app.services.scraper.http import PoliteHttp

    client = http or PoliteHttp()
    out: list[dict] = []
    errors: list[str] = []
    for target in LEVELS_TARGETS:
        url = f"{LEVELS_ORIGIN}{target['path']}"
        try:
            text = await client.get_text(
                url,
                referer=f"{LEVELS_ORIGIN}{target['html_path']}",
                timeout=30.0,
                accept="text/markdown, text/plain, */*",
            )
            parsed = parse_levels_md(
                text,
                key=target["key"],
                label=target["label"],
                html_path=target["html_path"],
                md_path=target["path"],
            )
            if parsed is None:
                errors.append(f"{target['key']}: empty parse")
                continue
            out.append(parsed.to_dict())
        except Exception as exc:
            errors.append(f"{target['key']}: {exc}"[:240])
    return out, errors
