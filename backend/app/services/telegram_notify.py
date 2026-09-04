"""User-facing Telegram bot copy. No HTTP — keep it testable and quiet."""

from __future__ import annotations

from datetime import datetime

from app.services.telegram import normalize_telegram_alias, telegram_chat_url
from app.services.vacancy_events import kind_label

DIGEST_CAP = 5


def vacancy_line(row) -> str:
    company = (getattr(row, "company", None) or "").strip() or "без компании"
    title = (getattr(row, "title", None) or "").strip() or "вакансия"
    return f"{company} — {title}"


def ping_line(row, days: int | None) -> str:
    line = vacancy_line(row)
    if days and days > 0:
        line += f" · {days} дн"
    alias = normalize_telegram_alias(getattr(row, "telegram_alias", None))
    if alias:
        line += f"\n@{alias}"
        url = telegram_chat_url(alias)
        if url:
            line += f"\n{url}"
    return line


def step_line(event, vacancy, when: str) -> str:
    label = (getattr(event, "label", None) or "").strip() or kind_label(event.kind)
    return f"{when} · {label} · {vacancy_line(vacancy)}"


def format_clock(instant: datetime) -> str:
    return instant.strftime("%H:%M")


def format_digest(
    *,
    vacancies: list,
    internships: list[str],
    hackathons: list[tuple[str, str | None]],
    pings: list[tuple[object, int | None]],
    steps: list[tuple[object, object, str]],
    origin: str | None = None,
) -> str | None:
    blocks: list[str] = []
    if vacancies:
        extra = len(vacancies) - DIGEST_CAP
        lines = [vacancy_line(row) for row in vacancies[:DIGEST_CAP]]
        head = f"Inbox · {len(vacancies)} новых"
        body = "\n".join(lines)
        if extra > 0:
            body += f"\nещё {extra}"
        blocks.append(f"{head}\n{body}")
    if internships:
        extra = len(internships) - DIGEST_CAP
        body = "\n".join(internships[:DIGEST_CAP])
        if extra > 0:
            body += f"\nещё {extra}"
        blocks.append(f"Стажировки открылись\n{body}")
    if hackathons:
        extra = len(hackathons) - DIGEST_CAP
        lines = []
        for title, url in hackathons[:DIGEST_CAP]:
            lines.append(f"{title}\n{url}" if url else title)
        body = "\n".join(lines)
        if extra > 0:
            body += f"\nещё {extra}"
        blocks.append(f"Хакатоны\n{body}")
    if pings:
        extra = len(pings) - DIGEST_CAP
        lines = [ping_line(row, days) for row, days in pings[:DIGEST_CAP]]
        body = "\n\n".join(lines)
        if extra > 0:
            body += f"\nещё {extra}"
        blocks.append(f"Пинг HR · «жду ответа»\n{body}")
    if steps:
        extra = len(steps) - DIGEST_CAP
        lines = [step_line(event, vacancy, when) for event, vacancy, when in steps[:DIGEST_CAP]]
        body = "\n".join(lines)
        if extra > 0:
            body += f"\nещё {extra}"
        blocks.append(f"Сегодня\n{body}")
    if not blocks:
        return None
    text = "\n\n".join(blocks)
    site = (origin or "").rstrip("/")
    if site:
        text += f"\n\n{site}"
    return text


def format_step_nudge(items: list[tuple[object, object, str]]) -> str | None:
    if not items:
        return None
    lines = [step_line(event, vacancy, when) for event, vacancy, when in items[:DIGEST_CAP]]
    extra = len(items) - DIGEST_CAP
    text = "Скоро\n" + "\n".join(lines)
    if extra > 0:
        text += f"\nещё {extra}"
    return text
