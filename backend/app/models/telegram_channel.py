from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class TelegramChannel(TimestampMixin, Base):
    """Shared pool of vacancy channels. Anyone may add; host account joins and parses."""

    __tablename__ = "telegram_channels"
    __table_args__ = (UniqueConstraint("username", name="uq_telegram_channels_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    added_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    invite_hash: Mapped[str | None] = mapped_column(String(128))
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    last_message_id: Mapped[int | None] = mapped_column(Integer)
    last_parsed_at: Mapped[datetime | None] = mapped_column(DateTime())
    added_url: Mapped[str | None] = mapped_column(String(512))
