from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class TelegramBotState(Base):
    """Singleton: Bot API token and getUpdates offset. Separate from host Telethon scrape."""

    __tablename__ = "telegram_bot_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    bot_token: Mapped[str | None] = mapped_column(Text)
    bot_username: Mapped[str | None] = mapped_column(String(64))
    update_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TelegramBotBind(TimestampMixin, Base):
    """One Hunt account ↔ one Telegram user. Messages are never mixed across people."""

    __tablename__ = "telegram_bot_binds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(64))
    paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    want_vacancies: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    want_internships: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    want_hackathons: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    want_steps: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    want_ping: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cursor_at: Mapped[datetime | None] = mapped_column(DateTime())
    last_digest_on: Mapped[str | None] = mapped_column(String(10))
    open_internship_slugs: Mapped[list] = mapped_column(JSON, default=list)


class TelegramLinkToken(Base):
    __tablename__ = "telegram_link_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class TelegramNotice(Base):
    """Dedupe so the bot does not repeat the same ping/step/digest."""

    __tablename__ = "telegram_notices"
    __table_args__ = (UniqueConstraint("user_id", "kind", "subject_key", name="uq_telegram_notice"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(128), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
