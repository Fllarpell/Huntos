from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.config import settings

_gates: dict[str, asyncio.Semaphore] = {}
_global: asyncio.Semaphore | None = None

_LIMIT = {
    "hh": "scraper_hh_concurrency",
    "hirehi": "scraper_hirehi_concurrency",
    "habr": "scraper_habr_concurrency",
    "getmatch": "scraper_getmatch_concurrency",
    "geekjob": "scraper_geekjob_concurrency",
    "career": "scraper_career_concurrency",
}

# Playwright sources share one Chrome. Separate semaphores would launch two browsers.
_BROWSER_SOURCES = frozenset({"hh", "getmatch"})
_BROWSER_KEY = "browser"


def reset_gates() -> None:
    global _global
    _gates.clear()
    _global = None


def gate_key(source: str) -> str:
    key = source or "hirehi"
    if key in _BROWSER_SOURCES:
        return _BROWSER_KEY
    return key


def source_concurrency(source: str) -> int:
    key = gate_key(source)
    if key == _BROWSER_KEY:
        return max(1, int(getattr(settings, "scraper_browser_concurrency", 1)))
    attr = _LIMIT.get(key, "scraper_hirehi_concurrency")
    return max(1, int(getattr(settings, attr, 1)))


def global_concurrency() -> int:
    return max(1, int(getattr(settings, "scraper_global_concurrency", 1)))


def _gate(source: str) -> asyncio.Semaphore:
    key = gate_key(source)
    if key not in _gates:
        _gates[key] = asyncio.Semaphore(source_concurrency(source))
    return _gates[key]


def _global_gate() -> asyncio.Semaphore:
    global _global
    if _global is None:
        _global = asyncio.Semaphore(global_concurrency())
    return _global


@asynccontextmanager
async def outbound_gate(source: str) -> AsyncIterator[None]:
    """Bound donor I/O: origin first (so Chrome waiters don't hog the NIC cap), then global."""
    async with _gate(source):
        async with _global_gate():
            yield
