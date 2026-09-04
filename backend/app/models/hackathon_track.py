from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class HackathonTrack(Base):
    """Per-user progress on a scraped hackathon event."""

    __tablename__ = "hackathon_tracks"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_hackathon_track_user_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("hackathon_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_status: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
