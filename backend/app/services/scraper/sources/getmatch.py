from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.services.company_icon import normalize_company_icon, resolve_getmatch_logotype
from app.services.scraper.http import PoliteHttp
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.getmatch_filters import GETMATCH_ORIGIN, listing_url_from_params, normalize_getmatch_params
from app.services.scraper.sources.hh import STEALTH_ARGS
from app.services.scraper.sources.hirehi import strip_html

_INITIAL = re.compile(r'"initialVacancy"\s*:\s*(\{)', re.I)
_NEXT_F = re.compile(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)')

LISTING_JS = """
() => {
  const links = [...document.querySelectorAll('a[href*="/vacancies/"]')];
  const seen = new Set();
  const jobs = [];
  for (const a of links) {
    const href = (a.href || "").split("?")[0];
    const m = href.match(/\\/vacancies\\/(\\d+)/);
    if (!m) continue;
    const id = m[1];
    if (seen.has(id)) continue;
    seen.add(id);
    const card = a.closest("article, li, [class*='card'], [class*='vacancy']") || a.parentElement;
    const text = (card && (card.innerText || card.textContent) || a.innerText || "").trim();
    const lines = text.split("\\n").map((s) => s.trim()).filter(Boolean);
    const img = card && card.querySelector("img");
    jobs.push({
      id,
      title: lines[0] || (a.innerText || "").trim(),
      url: href,
      company: lines[1] || "",
      salary: lines.find((s) => /₽|руб|\\$|€|от |до /i.test(s)) || "",
      company_icon: img ? (img.currentSrc || img.getAttribute("src") || "") : "",
    });
  }
  return jobs;
}
"""


def _slice_json_object(text: str, start: int) -> str | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _decode_next_f(html: str) -> str:
    parts: list[str] = []
    for chunk in _NEXT_F.findall(html or ""):
        try:
            parts.append(json.loads(f'"{chunk}"'))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def parse_initial_vacancy(html: str) -> dict:
    """Next.js RSC embeds the vacancy as initialVacancy on the job page."""
    for blob_source in (html or "", _decode_next_f(html or "")):
        match = _INITIAL.search(blob_source)
        if not match:
            continue
        blob = _slice_json_object(blob_source, match.start(1))
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and (data.get("id") or data.get("position")):
            return data
    return {}


def _skills(data: dict) -> list[str]:
    raw = data.get("skills_objects") or data.get("skills") or []
    out: list[str] = []
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                out.append(name)
    return out


def _work_format(data: dict) -> str | None:
    items = data.get("location_items") or data.get("location_requirements") or []
    formats = []
    for item in items:
        if not isinstance(item, dict):
            continue
        fmt = str(item.get("format") or "").lower()
        if fmt:
            formats.append(fmt)
    if "remote" in formats:
        return "удалённо"
    if "hybrid" in formats:
        return "гибрид"
    if "office" in formats:
        return "офис"
    return None


def _location(data: dict) -> str | None:
    items = data.get("location_items") or []
    labels = [str(item.get("label") or "").strip() for item in items if isinstance(item, dict)]
    labels = [item for item in labels if item]
    return ", ".join(labels) if labels else None


def _grade(data: dict) -> str | None:
    grade = data.get("grade") or data.get("level")
    if isinstance(grade, dict):
        grade = grade.get("slug") or grade.get("name")
    if grade:
        return str(grade).lower()
    return None


def normalize_getmatch_job(detail: dict, listing_item: dict | None = None) -> dict:
    data = {**(listing_item or {}), **detail}
    source_id = str(data.get("id") or data.get("source_id") or "")
    slug = data.get("url") or data.get("source_url") or ""
    if isinstance(slug, str) and slug.startswith("/"):
        url = f"{GETMATCH_ORIGIN}{slug}"
    elif isinstance(slug, str) and slug.startswith("http"):
        url = slug
    else:
        url = f"{GETMATCH_ORIGIN}/vacancies/{source_id}"
    company = data.get("company")
    company_name = company.get("name") if isinstance(company, dict) else company
    logo = data.get("company_icon")
    if isinstance(company, dict):
        logo = resolve_getmatch_logotype(company.get("logotype") or company.get("logo")) or logo
    skills = _skills(data)
    description = strip_html(data.get("offer_description") or data.get("description_html") or data.get("description") or "")
    salary_raw = data.get("salary_description") or data.get("salary_raw") or data.get("salary")
    salary_min, salary_max, currency = parse_salary(salary_raw)
    if data.get("salary_display_from") or data.get("salary_display_to"):
        try:
            salary_min = int(data["salary_display_from"]) if data.get("salary_display_from") else salary_min
            salary_max = int(data["salary_display_to"]) if data.get("salary_display_to") else salary_max
        except (TypeError, ValueError):
            pass
    work_format = _work_format(data) or data.get("work_format")
    grade = _grade(data)
    tags = ["getmatch"]
    if grade:
        tags.append(str(grade))
    if work_format:
        tags.append(work_format)
    tags.extend(skills)
    unique: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = str(tag).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(str(tag).strip())
    return {
        "source": "getmatch",
        "source_id": source_id,
        "source_url": url,
        "title": data.get("position") or data.get("title") or "Untitled",
        "company": company_name,
        "company_icon": normalize_company_icon(logo or data.get("company_icon"), page_url=url),
        "grade": grade,
        "work_format": work_format,
        "category": "development",
        "location": _location(data) or data.get("location"),
        "salary_raw": salary_raw,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency or data.get("salary_currency") or "RUB",
        "description": description or None,
        "requirements": description or None,
        "skills": skills,
        "tags": unique[:24],
        "raw_payload": data,
        "published_at": data.get("published_at"),
    }


class GetMatchSource:
    """GetMatch listing is a SPA; /api/vacancies is 401 without a session. Playwright for the list, HTML JSON for the card."""

    name = "getmatch"

    def __init__(self, http: PoliteHttp | None = None) -> None:
        self.http = http or PoliteHttp()
        self._playwright = None
        self._browser = None
        self._page = None

    async def open(self, query_params: dict | None = None) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Для GetMatch нужен Playwright. В backend: pip install playwright && playwright install chrome"
            ) from exc
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": True, "args": STEALTH_ARGS}
        try:
            self._browser = await self._playwright.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception:
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        context = await self._browser.new_context(
            locale="ru-RU",
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self._page = await context.new_page()
        self._page.set_default_timeout(25000)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    async def _scroll_listing(self) -> None:
        assert self._page is not None
        last = 0
        for _ in range(10):
            count = await self._page.evaluate(
                """() => document.querySelectorAll('a[href*="/vacancies/"]').length"""
            )
            if isinstance(count, int) and count > 0 and count <= last:
                break
            last = int(count or 0)
            await self._page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.35)
        await self._page.evaluate("() => window.scrollTo(0, 0)")

    async def _listing_page(self, url: str) -> tuple[list[dict], bool]:
        assert self._page is not None
        await self._page.goto(url, wait_until="domcontentloaded")
        try:
            await self._page.wait_for_selector('a[href*="/vacancies/"]', timeout=20_000)
        except Exception:
            return [], False
        await asyncio.sleep(0.4)
        await self._scroll_listing()
        jobs = await self._page.evaluate(LISTING_JS)
        has_next = bool(
            await self._page.query_selector(
                'a[rel="next"], button[aria-label*="следу"], a[href*="page="]:not([href*="page=1"])'
            )
        )
        if not has_next and len(jobs or []) >= 15:
            has_next = True
        return list(jobs or []), has_next

    async def search(self, query_params: dict, *, page: int, limit: int = 20) -> dict:
        if self._page is None:
            await self.open(query_params)
        assert self._page is not None
        data = normalize_getmatch_params(query_params)
        specialties = data.get("specialties") or ([data["specialty"]] if data.get("specialty") else [""])
        # GetMatch URL is one specialty. Wide hunt: walk each specialty on this crawl page.
        if len(specialties) > 1:
            if page > 5:
                return {"jobs": [], "has_more": False, "total_count": 0}
            merged: list[dict] = []
            seen: set[str] = set()
            any_next = False
            for sp in specialties:
                url = listing_url_from_params(query_params, specialty=sp or None)
                if page > 1:
                    sep = "&" if "?" in url else "?"
                    url = f"{url}{sep}page={page}"
                chunk, has_next = await self._listing_page(url)
                if has_next:
                    any_next = True
                for job in chunk:
                    key = str(job.get("id") or "")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    merged.append(job)
            return {"jobs": merged, "has_more": any_next, "total_count": len(merged)}

        url = listing_url_from_params(query_params)
        if page > 1:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}page={page}"
        jobs, has_next = await self._listing_page(url)
        if not jobs and page == 1:
            raise RuntimeError("GetMatch не отдал выдачу. Повтори позже или сузь фильтры.")
        return {"jobs": jobs[:limit] if limit else jobs, "has_more": has_next, "total_count": len(jobs)}

    async def detail(self, job_id: str | int, query_params: dict | None = None) -> dict:
        url = f"{GETMATCH_ORIGIN}/vacancies/{job_id}"
        html = await self.http.get_text(url, referer=listing_url_from_params(query_params or {}))
        posted = parse_initial_vacancy(html)
        posted["id"] = str(posted.get("id") or job_id)
        posted["source_url"] = url
        if not posted.get("position"):
            posted["title"] = posted.get("title") or ""
        return posted

    def normalize(self, detail: dict, listing_item: dict | None = None) -> dict:
        return normalize_getmatch_job(detail, listing_item)
