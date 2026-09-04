from __future__ import annotations

import asyncio
import random
import time
from urllib.parse import urlparse

import httpx

from app.config import settings

# Per-host clocks so HireHi and Habr can request at once. Same origin stays polite.
_last_by_host: dict[str, float] = {}
_clock = asyncio.Lock()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
]


def reset_http_clock() -> None:
    _last_by_host.clear()


def _host_key(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or parsed.netloc or "").lower()


class PoliteHttp:
    """httpx wrapper with UA rotation and jittered delays.

    Delay clock is per host: one HireHi origin, not one clock for the whole process.
    """

    async def get_json(
        self,
        url: str,
        *,
        params: dict | list[tuple[str, str]] | None = None,
        referer: str | None = None,
        timeout: float = 30.0,
    ) -> dict:
        response = await self._get(
            url,
            params=params,
            referer=referer,
            timeout=timeout,
            accept="application/json, text/plain, */*",
        )
        return response.json()

    async def get_text(
        self,
        url: str,
        *,
        params: dict | list[tuple[str, str]] | None = None,
        referer: str | None = None,
        timeout: float = 30.0,
        accept: str | None = None,
    ) -> str:
        response = await self._get(
            url,
            params=params,
            referer=referer,
            timeout=timeout,
            accept=accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        return response.text

    async def post_json(
        self,
        url: str,
        *,
        json: dict | None = None,
        referer: str | None = None,
        timeout: float = 30.0,
    ) -> dict:
        await self._sleep(url)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
        }
        if referer:
            headers["Referer"] = referer
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(url, json=json or {}, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _get(
        self,
        url: str,
        *,
        params: dict | list[tuple[str, str]] | None,
        referer: str | None,
        timeout: float,
        accept: str,
    ) -> httpx.Response:
        await self._sleep(url)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": accept,
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if referer:
            headers["Referer"] = referer
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response

    async def _sleep(self, url: str = "") -> None:
        host = _host_key(url)
        low = settings.scraper_min_delay_sec
        high = max(low, settings.scraper_max_delay_sec)
        delay = random.uniform(low, high)
        async with _clock:
            last = _last_by_host.get(host, 0.0)
            now = time.monotonic()
            wait = max(0.0, last + delay - now)
            _last_by_host[host] = now + wait
        if wait > 0:
            await asyncio.sleep(wait)
