from __future__ import annotations

import asyncio
import random
import time

import httpx

from app.config import settings

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
]


class PoliteHttp:
    """httpx wrapper with UA rotation and jittered delays."""

    def __init__(self) -> None:
        self._last_request_at = 0.0

    async def get_json(
        self,
        url: str,
        *,
        params: dict | list[tuple[str, str]] | None = None,
        referer: str | None = None,
        timeout: float = 30.0,
    ) -> dict:
        await self._sleep()
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if referer:
            headers["Referer"] = referer
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _sleep(self) -> None:
        low = settings.scraper_min_delay_sec
        high = max(low, settings.scraper_max_delay_sec)
        delay = random.uniform(low, high)
        elapsed = time.monotonic() - self._last_request_at
        remaining = delay - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()
