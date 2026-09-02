from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class TelegramPost(TimestampMixin, Base):
    """Canonical vacancy extracted from a channel post, then copied into each user's inbox."""

    __tablename__ = "telegram_posts"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_telegram_post_channel_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("telegram_channels.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime())
    raw_text: Mapped[str | None] = mapped_column(Text)
