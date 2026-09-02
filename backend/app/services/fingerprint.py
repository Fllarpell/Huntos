from __future__ import annotations

import re
import unicodedata

_NOISE = re.compile(r"[^a-zа-я0-9]+", re.IGNORECASE)
_ANON = {"", "nda", "confidential", "компания не указана", "без компании", "hidden"}


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower().replace("ё", "е")
    text = _NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def vacancy_fingerprint(title: str | None, company: str | None) -> str:
    company_n = _norm(company)
    if company_n in _ANON:
        company_n = "nda"
    title_n = _norm(title)[:80]
    return f"{company_n}|{title_n}"[:190]
