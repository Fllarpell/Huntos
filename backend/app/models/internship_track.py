from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class InternshipTrack(TimestampMixin, Base):
    """Per-user progress on a catalog internship or school program."""

    __tablename__ = "internship_tracks"
    __table_args__ = (UniqueConstraint("user_id", "program_slug", name="uq_internship_track_user_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program_slug: Mapped[str] = mapped_column(String(64), index=True)
    track_status: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime())
