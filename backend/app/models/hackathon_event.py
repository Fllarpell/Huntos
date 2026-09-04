from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class HackathonEvent(Base):
    """Scraped hackathon / competition card from public calendars."""

    __tablename__ = "hackathon_events"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_hackathon_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime())
    ends_at: Mapped[datetime | None] = mapped_column(DateTime())
    registration_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    event_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    format: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[str | None] = mapped_column(String(512))
    prize_text: Mapped[str | None] = mapped_column(String(128))
    organizer: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(1024))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    check_error: Mapped[str | None] = mapped_column(Text)
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
