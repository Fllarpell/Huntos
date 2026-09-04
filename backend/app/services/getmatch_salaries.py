"""GetMatch public salary snapshot (getmatch.ru/api/salaries) — anonymous overall IT."""

from __future__ import annotations

GETMATCH_SALARIES_URL = "https://getmatch.ru/salaries"
GETMATCH_SALARIES_API = "https://getmatch.ru/api/salaries"
GETMATCH_ORIGIN = "https://getmatch.ru"


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if number > 0 else None
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            return None
        try:
            number = int(digits)
        except ValueError:
            return None
        return number if number > 0 else None
    return None


def _to_monthly_rub(value: int | None) -> int | None:
    """Anonymous API returns thousands (160 → 160_000). Full rubles pass through."""
    if value is None:
        return None
    if value < 10_000:
        return value * 1000
    return value


def parse_getmatch_salaries(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None
    p25 = _to_monthly_rub(_as_int(payload.get("percentile_25")))
    median = _to_monthly_rub(_as_int(payload.get("percentile_50")))
    p90 = _to_monthly_rub(_as_int(payload.get("percentile_90")))
    if p25 is None or median is None or p90 is None:
        return None
    hist = payload.get("histogram") if isinstance(payload.get("histogram"), dict) else {}
    counts = hist.get("y") if isinstance(hist, dict) else None
    n = None
    if isinstance(counts, list):
        nums = [_as_int(item) or 0 for item in counts]
        total = sum(nums)
        n = total if total > 0 else None
    return {
        "key": "getmatch_all",
        "grade": None,
        "label": "IT · все грейды",
        "n": n,
        "p25": p25,
        "median": median,
        "p75": None,
        "p90": p90,
        "currency": "RUB",
        "period": "month",
        "source": "getmatch_salaries",
        "url": GETMATCH_SALARIES_URL,
        "attribution": "GetMatch · зарплаты (анонимный срез, p25 / медиана / p90)",
        "note": "Публичный API без логина отдаёт только общий IT-срез. p90, не p75.",
    }


async def fetch_getmatch_salaries(http=None) -> tuple[list[dict], list[str]]:
    from app.services.scraper.http import PoliteHttp

    client = http or PoliteHttp()
    errors: list[str] = []
    try:
        payload = await client.get_json(GETMATCH_SALARIES_API, referer=GETMATCH_SALARIES_URL)
    except Exception as exc:  # noqa: BLE001 — donor page, keep the rest of market
        return [], [str(exc)]
    row = parse_getmatch_salaries(payload if isinstance(payload, dict) else {})
    if not row:
        errors.append("getmatch salaries: empty payload")
        return [], errors
    return [row], errors
