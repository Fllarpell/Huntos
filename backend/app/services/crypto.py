from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet | None:
    key = (settings.token_fernet_key or "").strip()
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


@lru_cache(maxsize=1)
def _cached_fernet() -> Fernet | None:
    return _fernet()


def reset_fernet_cache() -> None:
    _cached_fernet.cache_clear()


def seal(value: str | None) -> str | None:
    if not value:
        return value
    box = _cached_fernet()
    if box is None or value.startswith("gAAAA"):
        return value
    return box.encrypt(value.encode("utf-8")).decode("ascii")


def unseal(value: str | None) -> str | None:
    if not value:
        return value
    box = _cached_fernet()
    if box is None or not value.startswith("gAAAA"):
        return value
    try:
        return box.decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return value
