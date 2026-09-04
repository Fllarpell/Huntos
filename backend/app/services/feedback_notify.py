"""Ping the host when someone files a bug or an idea. Failures stay quiet."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.telegram_bot import TelegramBotBind
from app.models.user import User
from app.services.telegram_bot import bot_token, get_state, send_text

log = logging.getLogger(__name__)

KIND_LABEL = {"bug": "ошибка", "idea": "пожелание"}
PAGE_LABEL = {
    "/": "Inbox",
    "/pipeline": "Воронка",
    "/time": "Время",
    "/contacts": "Контакты",
    "/internships": "Стажировки",
    "/hackathons": "Хакатоны",
    "/thesis": "Тезис",
    "/settings": "Настройки",
}


def page_label(page: str | None) -> str | None:
    text = (page or "").strip()
    if not text:
        return None
    return PAGE_LABEL.get(text, text)


def format_feedback_message(
    *,
    kind: str,
    body: str,
    email: str,
    page: str | None = None,
    contact_name: str | None = None,
    reply_to: str | None = None,
) -> str:
    label = KIND_LABEL.get(kind, kind)
    lines = [label, email]
    if page:
        lines.append(f"экран {page_label(page)}")
    if contact_name:
        lines.append(f"кто {contact_name}")
    if reply_to:
        lines.append(f"ответ {reply_to}")
    lines.append("")
    lines.append(body.strip())
    return "\n".join(lines).strip()


def feedback_subject(kind: str, page: str | None = None) -> str:
    label = KIND_LABEL.get(kind, kind)
    screen = page_label(page)
    if screen:
        return f"HuntOS · {label} · {screen}"
    return f"HuntOS · {label}"


def parse_chat_id(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def send_smtp(subject: str, body: str) -> bool:
    host = (settings.smtp_host or "").strip()
    user = (settings.smtp_user or "").strip()
    to = (settings.feedback_email_to or user).strip()
    password = settings.smtp_password or ""
    if not host or not to:
        return False
    sender = (settings.smtp_from or user or to).strip()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    port = settings.smtp_port or 587
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=12) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
    except Exception:
        log.warning("feedback email failed to=%s", to, exc_info=True)
        return False
    return True


async def telegram_destinations(session: AsyncSession) -> list[int]:
    extra = parse_chat_id(settings.feedback_telegram_chat_id)
    rows = (
        await session.execute(
            select(TelegramBotBind.chat_id)
            .join(User, User.id == TelegramBotBind.user_id)
            .where(
                User.is_host.is_(True),
                TelegramBotBind.paused.is_(False),
                TelegramBotBind.chat_id.is_not(None),
            )
        )
    ).all()
    seen: set[int] = set()
    out: list[int] = []
    for chat_id in [extra, *[row[0] for row in rows]]:
        if chat_id is None or chat_id in seen:
            continue
        seen.add(chat_id)
        out.append(chat_id)
    return out


async def notify_feedback(
    session: AsyncSession,
    *,
    kind: str,
    body: str,
    email: str,
    page: str | None = None,
    contact_name: str | None = None,
    reply_to: str | None = None,
) -> None:
    text = format_feedback_message(
        kind=kind,
        body=body,
        email=email,
        page=page,
        contact_name=contact_name,
        reply_to=reply_to,
    )
    subject = feedback_subject(kind, page)
    state = await get_state(session)
    token = bot_token(state)
    if token:
        for chat_id in await telegram_destinations(session):
            try:
                await send_text(token, chat_id, text)
            except Exception:
                log.warning("feedback telegram failed chat=%s", chat_id, exc_info=True)
    send_smtp(subject, text)
