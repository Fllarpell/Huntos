from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.sql import ColumnElement

from app.config import settings


def fold_expr(column) -> ColumnElement:
    """Case-fold text in SQL. SQLite lower() is ASCII-only, so Cyrillic needs unicode_lower."""
    coalesced = func.coalesce(column, "")
    if settings.is_sqlite():
        return func.unicode_lower(coalesced)
    return func.lower(coalesced)
