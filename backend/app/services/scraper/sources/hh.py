from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.services.company_icon import normalize_company_icon
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.hh_filters import HH_ORIGIN, listing_url_from_params, normalize_hh_params
from app.services.scraper.sources.hirehi import strip_html

log = logging.getLogger(__name__)

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-notifications",
    "--disable-dev-shm-usage",
]

_SPLIT_REQUIRE = re.compile(r"требован", re.I)
_SPLIT_TASKS = re.compile(r"обязанност|задач", re.I)
_SPLIT_COND = re.compile(r"услов|предлагаем|мы предлагаем", re.I)

LISTING_JS = """
() => {
  const cards = [...document.querySelectorAll('[data-qa="vacancy-serp__vacancy"], [data-qa="serp-item"]')];
  return cards.map((card) => {
    const link = card.querySelector('a[href*="/vacancy/"]');
    const href = (link && link.href) ? link.href.split("?")[0] : "";
    const idMatch = href.match(/\\/vacancy\\/(\\d+)/) || String(card.id || "").match(/(\\d+)/);
    const text = (sel) => {
      const el = card.querySelector(sel);
      return (el && (el.innerText || el.textContent) || "").trim();
    };
    const pickLogo = (root) => {
      const sels = [
        '[data-qa="vacancy-serp__vacancy-employer-logo"] img',
        'img[data-qa*="employer-logo"]',
        'img[src*="employer-logo"]',
        'img[src*="company-logo"]',
      ];
      for (const sel of sels) {
        const el = root.querySelector(sel);
        if (!el) continue;
        const src = (el.currentSrc || el.getAttribute("src") || "").trim();
        if (src && !src.startsWith("data:")) return src;
      }
      return "";
    };
    return {
      id: (idMatch && idMatch[1]) || card.id || "",
      title: text('[data-qa="serp-item__title-text"]') || (link && link.innerText) || "",
      url: href,
      company: text('[data-qa="vacancy-serp__vacancy-employer-text"]'),
      company_icon: pickLogo(card),
      salary: text('[data-qa="vacancy-serp__compensation"]'),
      experience: text('[data-qa*="vacancy-serp__vacancy-work-experience"]'),
      address: text('[data-qa="vacancy-serp__vacancy-address"]'),
    };
  }).filter((row) => row.id || row.title);
}
"""

DETAIL_JS = """
() => {
  const text = (sel) => {
    const el = document.querySelector(sel);
    return (el && (el.innerText || el.textContent) || "").trim();
  };
  const skills = [...document.querySelectorAll('[data-qa="skills-element"], [data-qa="vacancy-key-skills"] span')]
    .map((el) => (el.innerText || "").trim())
    .filter(Boolean);
  const desc = document.querySelector('[data-qa="vacancy-description"], [data-qa="vacancy-branded-description-content"]');
  const pickLogo = (root) => {
    const sels = [
      '[data-qa="vacancy-company-logo"] img',
      'img[data-qa="vacancy-company-logo"]',
      'img[data-qa*="employer-logo"]',
      'img[src*="employer-logo"]',
      'img[src*="company-logo"]',
    ];
    for (const sel of sels) {
      const el = root.querySelector(sel);
      if (!el) continue;
      const src = (el.currentSrc || el.getAttribute("src") || "").trim();
      if (src && !src.startsWith("data:")) return src;
    }
    return "";
  };
  return {
    title: text('[data-qa="vacancy-title"]'),
    salary: text('[data-qa="vacancy-salary"]'),
    company: text('[data-qa="vacancy-company-name"]'),
    company_icon: pickLogo(document),
    experience: text('[data-qa="vacancy-experience"]'),
    employment: text('[data-qa="vacancy-view-employment-mode"]'),
    schedule: text('[data-qa="vacancy-view-work-schedule"]'),
    address: text('[data-qa="vacancy-view-raw-address"]'),
    published_at: text('[data-qa="vacancy-creation-time"]'),
    description: desc ? (desc.innerText || "") : "",
    description_html: desc ? desc.innerHTML : "",
    skills,
    url: location.href.split("?")[0],
  };
}
"""


def _map_grade(experience: str | None) -> str | None:
    text = (experience or "").lower()
    if not text:
        return None
    if "нет опыта" in text or "noexperience" in text.replace(" ", ""):
        return "intern"
    if "1" in text and "3" in text:
        return "junior"
    if "3" in text and "6" in text:
        return "middle"
    if "более 6" in text or "6+" in text or "morethan6" in text.replace(" ", ""):
        return "senior"
    return None


def _map_format(schedule: str | None, description: str = "", address: str = "") -> str | None:
    text = f"{schedule or ''} {description} {address}".lower()
    if re.search(r"гибрид|hybrid|частично\s+удал|смешанн\w+\s+формат", text):
        return "гибрид"
    if re.search(r"удал[её]н|remote|дистанц", text):
        return "удалённо"
    if re.search(r"вахт|fly.?in.?fly.?out", text):
        return "вахта"
    if re.search(r"гибк|flexible", text):
        return "гибрид"
    if re.search(r"полный день|офис|сменн", text):
        return "офис"
    return None


def _split_description(description: str) -> tuple[str, str, str]:
    if not description:
        return "", "", ""
    sections = {"requirements": "", "responsibilities": "", "conditions": ""}
    current = "description"
    lines: list[str] = []

    def flush() -> None:
        if lines and current in sections:
            sections[current] = "\n".join(lines).strip()

    for line in description.splitlines():
        normalized = line.strip().lower()
        nxt = None
        if _SPLIT_REQUIRE.search(normalized):
            nxt = "requirements"
        elif _SPLIT_TASKS.search(normalized):
            nxt = "responsibilities"
        elif _SPLIT_COND.search(normalized):
            nxt = "conditions"
        if nxt:
            flush()
            current = nxt
            lines = []
            continue
        lines.append(line)
    flush()
    return sections["requirements"], sections["responsibilities"], sections["conditions"]


def normalize_hh_job(detail: dict, listing_item: dict | None = None) -> dict:
    data = {**(listing_item or {}), **{k: v for k, v in detail.items() if v}}
    source_id = str(data.get("id") or "")
    title = data.get("title") or "Untitled"
    description = strip_html(data.get("description") or data.get("description_html"))
    requirements, tasks, conditions = _split_description(description)
    if data.get("requirements"):
        requirements = data["requirements"]
    skills = data.get("skills") or data.get("key_skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    salary_raw = data.get("salary") or None
    salary_min, salary_max, currency = parse_salary(salary_raw)
    experience = data.get("experience") or ""
    schedule = data.get("schedule") or ""
    location = data.get("address") or None
    url = (data.get("url") or "").split("?")[0]
    if not url and source_id:
        url = f"{HH_ORIGIN}/vacancy/{source_id}"
    tags = [x for x in (experience, schedule, _map_format(schedule, description, location or "")) if x]
    tags.extend(skills)
    unique: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = tag.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(tag.strip())
    return {
        "source": "hh",
        "source_id": source_id,
        "source_url": url,
        "title": title,
        "company": data.get("company") or data.get("employer") or None,
        "company_icon": normalize_company_icon(
            data.get("company_icon") or data.get("logo"),
            page_url=url or HH_ORIGIN,
        ),
        "grade": _map_grade(experience),
        "work_format": _map_format(schedule, description, location or ""),
        "category": "development",
        "location": location,
        "country": "Россия",
        "salary_raw": salary_raw,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency or "RUB",
        "description": description,
        "requirements": requirements or None,
        "tasks_html": tasks or None,
        "conditions_html": conditions or None,
        "skills": skills,
        "tags": unique[:24],
        "raw_payload": data,
        "published_at": data.get("published_at") or None,
    }


class HhSource:
    """hh.ru via Playwright. Public JSON search is 403 without employer OAuth."""

    name = "hh"

    def __init__(self, http: Any = None) -> None:  # http unused — keeps engine signature
        self._playwright = None
        self._browser = None
        self._page = None
        self._headed = False

    async def open(self, query_params: dict | None = None) -> None:
        params = normalize_hh_params(query_params)
        self._headed = bool(params.get("headed"))
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Для hh.ru нужен Playwright. В backend: pip install playwright && playwright install chrome"
            ) from exc
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": not self._headed, "args": STEALTH_ARGS}
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

    def normalize(self, detail: dict, listing_item: dict | None = None) -> dict:
        return normalize_hh_job(detail, listing_item)

    async def search(self, query_params: dict, *, page: int, limit: int = 50) -> dict:
        if self._page is None:
            await self.open(query_params)
        assert self._page is not None
        url = listing_url_from_params(query_params, page=max(0, page - 1))
        await self._page.goto(url, wait_until="domcontentloaded")
        await self._dismiss_cookies()
        await self._wait_past_captcha()
        self._raise_if_blocked()
        timeout_ms = 120_000 if self._headed else 20_000
        try:
            await self._page.wait_for_selector(
                '[data-qa="vacancy-serp__vacancy"], [data-qa="serp-item"]',
                timeout=timeout_ms,
            )
        except Exception as exc:
            self._raise_if_blocked()
            raise RuntimeError("hh.ru не отдал выдачу. Включи «показать Chrome» в поиске или пройди капчу.") from exc
        await asyncio.sleep(0.8)
        jobs = await self._page.evaluate(LISTING_JS)
        has_next = bool(await self._page.query_selector('[data-qa="pager-next"]'))
        return {"jobs": jobs[:limit], "has_more": has_next, "total_count": len(jobs)}

    async def detail(self, job_id: str | int, query_params: dict | None = None) -> dict:
        if self._page is None:
            await self.open(query_params)
        assert self._page is not None
        await self._page.goto(f"{HH_ORIGIN}/vacancy/{job_id}", wait_until="domcontentloaded")
        await self._dismiss_cookies()
        await self._wait_past_captcha()
        self._raise_if_blocked()
        timeout_ms = 120_000 if self._headed else 20_000
        try:
            await self._page.wait_for_selector(
                '[data-qa="vacancy-title"], [data-qa="vacancy-description"]',
                timeout=timeout_ms,
            )
        except Exception as exc:
            raise RuntimeError(f"Не открылась вакансия hh.ru {job_id}") from exc
        await asyncio.sleep(0.6)
        data = await self._page.evaluate(DETAIL_JS)
        data["id"] = str(job_id)
        return data

    async def _dismiss_cookies(self) -> None:
        assert self._page is not None
        btn = await self._page.query_selector('[data-qa="cookies-policy-informer-accept"]')
        if btn:
            try:
                await btn.click(timeout=2000)
            except Exception:
                pass

    async def _wait_past_captcha(self) -> None:
        if self._page is None or not self._headed:
            return
        if not self._is_blocked():
            return
        try:
            await self._page.wait_for_url(
                lambda url: not any(mark in url.lower() for mark in ("captcha", "vpncheck", "vpncheeck")),
                timeout=120_000,
            )
        except Exception:
            pass

    def _is_blocked(self) -> bool:
        if self._page is None:
            return False
        url = (self._page.url or "").lower()
        return any(mark in url for mark in ("captcha", "vpncheck", "vpncheeck", "access-denied"))

    def _raise_if_blocked(self) -> None:
        if self._is_blocked():
            raise RuntimeError(
                "hh.ru показал капчу/блокировку. Включи «показать Chrome» в настройках поиска и пройди проверку."
            )
