from __future__ import annotations

import re


_NUM = re.compile(r"\d[\d\s\u00a0]*")


def parse_salary(raw: str | None) -> tuple[int | None, int | None, str | None]:
    if not raw:
        return None, None, None
    text = raw.strip()
    lower = text.lower()
    if "не указан" in lower:
        return None, None, None

    currency = "RUB"
    if "$" in text or "usd" in lower:
        currency = "USD"
    elif "€" in text or "eur" in lower:
        currency = "EUR"
    elif "₸" in text or "kzt" in lower:
        currency = "KZT"

    nums = [int(re.sub(r"\D", "", m.group(0))) for m in _NUM.finditer(text)]
    nums = [n for n in nums if n >= 100]
    if not nums:
        return None, None, currency

    if lower.startswith("от") or " от " in f" {lower}":
        return nums[0], nums[1] if len(nums) > 1 else None, currency
    if lower.startswith("до") or " до " in f" {lower}":
        return None, nums[0], currency
    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1]), currency
    return nums[0], nums[0], currency
