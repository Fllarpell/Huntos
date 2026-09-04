from __future__ import annotations

import json
import re
from html import unescape

from app.services.company_icon import logo_from_hiring_org
from app.services.scraper.sources.hirehi import strip_html

_JSONLD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)


def first_job_posting(node: object) -> dict | None:
    if isinstance(node, list):
        for item in node:
            found = first_job_posting(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None
    types = node.get("@type")
    labels = types if isinstance(types, list) else [types]
    if any(str(label).lower() == "jobposting" for label in labels if label):
        return node
    graph = node.get("@graph")
    if graph is not None:
        return first_job_posting(graph)
    return None


_PERIOD_UNITS = frozenset({"hour", "day", "week", "month", "year"})


def _money_token(raw: object) -> str:
    text = str(raw or "").strip()
    if not text or text.lower() in _PERIOD_UNITS:
        return ""
    return text


def _salary_raw(job: dict) -> str:
    salary = job.get("baseSalary")
    if not isinstance(salary, dict):
        return ""
    currency = _money_token(salary.get("currency"))
    value = salary.get("value")
    if isinstance(value, dict):
        lo = value.get("minValue") or value.get("value")
        hi = value.get("maxValue") or lo
        # unitText is MONTH/YEAR, not a currency — don't leak it into parse_salary.
        suffix = currency
        if lo is not None and hi is not None and str(lo) != str(hi):
            return f"от {lo} до {hi} {suffix}".strip()
        if lo is not None:
            return f"{lo} {suffix}".strip()
        if hi is not None:
            return f"до {hi} {suffix}".strip()
        return suffix
    if value is not None:
        return f"{value} {currency}".strip()
    return currency


def extract_job_posting(html: str, *, page_url: str | None = None) -> dict[str, str]:
    """schema.org JobPosting from a vacancy HTML page."""
    out: dict[str, str] = {}
    for script in _JSONLD.findall(html or ""):
        try:
            data = json.loads(unescape(script))
        except json.JSONDecodeError:
            continue
        job = first_job_posting(data)
        if not job:
            continue
        title = str(job.get("title") or "").strip()
        org = job.get("hiringOrganization")
        company = ""
        if isinstance(org, dict):
            company = str(org.get("name") or "").strip()
            logo = logo_from_hiring_org(org, page_url=page_url)
            if logo:
                out["company_icon"] = logo
        elif isinstance(org, str):
            company = org.strip()
        description = strip_html(str(job.get("description") or ""))
        salary_raw = _salary_raw(job)
        if title:
            out["title"] = title[:512]
        if company:
            out["company"] = company[:255]
        if description:
            out["description"] = description[:20000]
        if salary_raw:
            out["salary_raw"] = salary_raw[:128]
        skills = job.get("skills") or job.get("knowsAbout") or []
        if isinstance(skills, str):
            out["skills"] = skills
        elif isinstance(skills, list):
            names = []
            for item in skills:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                elif isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]).strip())
            if names:
                out["skills"] = ", ".join(names)
        loc = job.get("jobLocation")
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                city = addr.get("addressLocality") or ""
                if city:
                    out["location"] = str(city)
            elif isinstance(addr, str) and addr.strip():
                out["location"] = addr.strip()
        elif isinstance(loc, list) and loc:
            out["location"] = str(loc[0])
        remote = job.get("jobLocationType") or ""
        if "TELECOMMUTE" in str(remote).upper():
            out["work_format"] = "удалённо"
        if job.get("datePosted"):
            out["published_at"] = str(job["datePosted"])
        break
    return out
