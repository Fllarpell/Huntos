from __future__ import annotations

import secrets

from app.prompts.resume import PARSE_SYSTEM, PARSE_USER
from app.services.scoring.llm import LLMConfig, LLMError, complete, extract_json

PARSE_CHARS = 14000


def issue_share_id() -> str:
    return secrets.token_urlsafe(16)


def empty_resume() -> dict:
    return {
        "name": "",
        "headline": "",
        "email": "",
        "phone": "",
        "telegram": "",
        "location": "",
        "links": [],
        "summary": "",
        "about_items": [],
        "skills": [],
        "skill_groups": [],
        "experience": [],
        "education": [],
        "languages": [],
        "courses": [],
        "hackathons": [],
    }


def _str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _line_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    if isinstance(value, list):
        return [_str(item) for item in value if _str(item)]
    return []


def _csv_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [_str(item) for item in value if _str(item)]
    return []


def _bullet(item: object) -> dict:
    if isinstance(item, str):
        return {"text": item.strip(), "children": []}
    row = item if isinstance(item, dict) else {}
    children = row.get("children")
    if isinstance(children, str):
        child_list = [line.strip().lstrip("•-–* ") for line in children.splitlines() if line.strip()]
    else:
        child_list = _line_list(children)
    return {"text": _str(row.get("text")), "children": child_list}


def _experience(item: object) -> dict:
    row = item if isinstance(item, dict) else {}
    bullets = row.get("bullets")
    if isinstance(bullets, str):
        bullet_list = [_bullet(line.strip().lstrip("•-–* ")) for line in bullets.splitlines() if line.strip()]
    elif isinstance(bullets, list):
        bullet_list = [_bullet(entry) for entry in bullets]
    else:
        bullet_list = []
    return {
        "company": _str(row.get("company")),
        "title": _str(row.get("title")),
        "period": _str(row.get("period")),
        "context": _str(row.get("context")),
        "bullets": bullet_list,
    }


def _education(item: object) -> dict:
    row = item if isinstance(item, dict) else {}
    return {
        "school": _str(row.get("school")),
        "degree": _str(row.get("degree")),
        "period": _str(row.get("period")),
        "bullets": _line_list(row.get("bullets")),
    }


def _about_item(item: object) -> dict:
    if isinstance(item, str):
        label, sep, rest = item.partition(":")
        if sep and len(label) <= 40:
            return {"label": label.strip(), "text": rest.strip()}
        return {"label": "", "text": item.strip()}
    row = item if isinstance(item, dict) else {}
    return {"label": _str(row.get("label")), "text": _str(row.get("text"))}


def _skill_group(item: object) -> dict:
    if isinstance(item, str):
        label, sep, rest = item.partition(":")
        if sep and len(label) <= 48:
            return {"label": label.strip(), "items": rest.strip()}
        return {"label": "", "items": item.strip()}
    row = item if isinstance(item, dict) else {}
    items = row.get("items")
    if isinstance(items, list):
        packed = ", ".join(_str(part) for part in items if _str(part))
    else:
        packed = _str(items)
    return {"label": _str(row.get("label") or row.get("name")), "items": packed}


def normalize_resume(raw: object | None) -> dict:
    src = raw if isinstance(raw, dict) else {}
    doc = empty_resume()
    doc["name"] = _str(src.get("name"))
    doc["headline"] = _str(src.get("headline"))
    doc["email"] = _str(src.get("email"))
    doc["phone"] = _str(src.get("phone"))
    doc["telegram"] = _str(src.get("telegram"))
    doc["location"] = _str(src.get("location"))
    doc["links"] = _line_list(src.get("links"))
    doc["summary"] = _str(src.get("summary"))
    about = src.get("about_items")
    doc["about_items"] = [_about_item(item) for item in about] if isinstance(about, list) else []
    languages = _csv_list(src.get("languages"))
    doc["languages"] = languages
    if languages and not any(_str(item.get("label")).casefold().startswith("язык") for item in doc["about_items"]):
        doc["about_items"].append({"label": "Языки", "text": ", ".join(languages)})
    doc["skills"] = _csv_list(src.get("skills"))
    groups = src.get("skill_groups")
    doc["skill_groups"] = [_skill_group(item) for item in groups] if isinstance(groups, list) else []
    if not any(g["label"] or g["items"] for g in doc["skill_groups"]) and doc["skills"]:
        doc["skill_groups"] = [{"label": "", "items": ", ".join(doc["skills"])}]
    experience = src.get("experience")
    doc["experience"] = [_experience(item) for item in experience] if isinstance(experience, list) else []
    education = src.get("education")
    doc["education"] = [_education(item) for item in education] if isinstance(education, list) else []
    doc["courses"] = _line_list(src.get("courses"))
    doc["hackathons"] = _line_list(src.get("hackathons"))
    return doc


def flatten_resume(raw: object | None) -> str:
    doc = normalize_resume(raw)
    lines: list[str] = []
    if doc["name"]:
        lines.append(doc["name"])
    if doc["headline"]:
        lines.append(doc["headline"])
    contacts = [
        part
        for part in (doc["location"], doc["phone"], doc["telegram"], doc["email"])
        if part
    ]
    if contacts:
        lines.append(" | ".join(contacts))
    if doc["links"]:
        lines.append(" | ".join(doc["links"]))
    if doc["summary"]:
        lines.extend(["", "Обо мне", doc["summary"]])
    for item in doc["about_items"]:
        if not item["label"] and not item["text"]:
            continue
        if item["label"]:
            lines.append(f"- {item['label']}: {item['text']}")
        else:
            lines.append(f"- {item['text']}")
    groups = [g for g in doc["skill_groups"] if g["label"] or g["items"]]
    if groups:
        lines.extend(["", "Технические навыки"])
        for group in groups:
            if group["label"]:
                lines.append(f"- {group['label']}: {group['items']}")
            else:
                lines.append(f"- {group['items']}")
    elif doc["skills"]:
        lines.extend(["", "Skills: " + ", ".join(doc["skills"])])
    jobs = [
        job
        for job in doc["experience"]
        if job["company"] or job["title"] or any(b["text"] or b["children"] for b in job["bullets"])
    ]
    if jobs:
        lines.extend(["", "Опыт работы"])
        for job in jobs:
            head = " — ".join(part for part in (job["title"], job["company"]) if part)
            if job["period"]:
                head = f"{head} ({job['period']})" if head else job["period"]
            if head:
                lines.append(head)
            if job["context"]:
                lines.append(job["context"])
            for bullet in job["bullets"]:
                if bullet["text"]:
                    lines.append(f"- {bullet['text']}")
                for child in bullet["children"]:
                    lines.append(f"  - {child}")
    schools = [row for row in doc["education"] if row["school"] or row["degree"]]
    if schools:
        lines.extend(["", "Образование"])
        for row in schools:
            head = ", ".join(part for part in (row["degree"], row["school"]) if part)
            if row["period"]:
                head = f"{head} ({row['period']})" if head else row["period"]
            if head:
                lines.append(head)
            for bullet in row["bullets"]:
                lines.append(f"- {bullet}")
    if doc["courses"]:
        lines.extend(["", "Повышение квалификации"])
        lines.extend(f"- {item}" for item in doc["courses"])
    if doc["hackathons"]:
        lines.extend(["", "Хакатоны"])
        lines.extend(f"- {item}" for item in doc["hackathons"])
    return "\n".join(lines).strip()


def merge_adapted_experience(base: object, adapted: object) -> dict:
    doc = normalize_resume(base)
    jobs = list(doc["experience"])
    incoming = [_experience(item) for item in adapted] if isinstance(adapted, list) else []
    used: set[int] = set()

    def find_job(src: dict, fallback: int) -> int | None:
        company = src["company"].casefold()
        title = src["title"].casefold()
        if company:
            for i, orig in enumerate(jobs):
                if i in used:
                    continue
                if orig["company"].casefold() != company:
                    continue
                if not title or not orig["title"] or orig["title"].casefold() == title:
                    return i
            return None
        if 0 <= fallback < len(jobs) and fallback not in used:
            return fallback
        return None

    for index, src in enumerate(incoming):
        idx = find_job(src, index)
        if idx is None:
            continue
        bullets = [row for row in src["bullets"] if row["text"] or row["children"]]
        if not bullets:
            continue
        used.add(idx)
        jobs[idx] = {**jobs[idx], "bullets": bullets}
    doc["experience"] = jobs
    return doc


def resume_has_content(raw: object | None) -> bool:
    return bool(flatten_resume(raw))


def resume_is_empty(raw: object | None) -> bool:
    return not resume_has_content(raw)


def _llm_ready(cfg: LLMConfig | None) -> bool:
    if cfg is None:
        return False
    if cfg.provider == "ollama":
        return bool(cfg.model)
    return bool(cfg.openai_api_key)


async def fill_resume_from_text(
    text: str,
    display_name: str | None = None,
    cfg: LLMConfig | None = None,
) -> dict:
    fallback = hydrate_from_text(text, display_name)
    blob = (text or "").strip()
    if not blob or not _llm_ready(cfg):
        return fallback
    try:
        raw = await complete(
            cfg,
            system=PARSE_SYSTEM,
            user=PARSE_USER.format(text=blob[:PARSE_CHARS]),
            json_mode=True,
        )
        doc = normalize_resume(extract_json(raw))
        if resume_is_empty(doc):
            return fallback
        if not doc["name"] and display_name:
            doc["name"] = display_name.strip()
        return doc
    except (LLMError, Exception):  # noqa: BLE001
        return fallback


def hydrate_from_text(text: str, display_name: str | None = None) -> dict:
    doc = empty_resume()
    blob = (text or "").strip()
    if not blob:
        if display_name:
            doc["name"] = display_name.strip()
        return doc
    lines = [line.strip() for line in blob.splitlines() if line.strip()]
    name = (display_name or "").strip()
    rest = blob
    if lines and len(lines[0]) <= 80 and " " in lines[0] and not name:
        name = lines[0]
        rest = "\n".join(lines[1:]).strip()
    elif lines and len(lines[0]) <= 48 and not name and len(lines) > 1:
        name = lines[0]
        rest = "\n".join(lines[1:]).strip()
    doc["name"] = name
    doc["summary"] = rest
    return doc


def resume_for_llm(profile) -> str:  # noqa: ANN001
    structured = flatten_resume(getattr(profile, "resume_json", None) if profile else None)
    if structured:
        return structured
    return ((getattr(profile, "resume_text", None) if profile else None) or "").strip()
