from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class PingSlot(TimestampMixin, Base):
    """One calendar block per mature ping queue (thesis pack), not N events."""

    __tablename__ = "ping_slots"
    __table_args__ = (UniqueConstraint("user_id", "scope", name="uq_ping_slots_user_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thesis_id: Mapped[int | None] = mapped_column(ForeignKey("hunt_theses.id", ondelete="SET NULL"), index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="без тезиса")
    vacancy_ids: Mapped[list] = mapped_column(JSON, default=list)
    card_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ping_at: Mapped[datetime | None] = mapped_column(DateTime())
    google_event_id: Mapped[str | None] = mapped_column(String(128))
    google_sync_error: Mapped[str | None] = mapped_column(Text)
    synced_count: Mapped[int | None] = mapped_column(Integer)
    synced_ping_at: Mapped[datetime | None] = mapped_column(DateTime())


def ping_scope(thesis_id: int | None) -> str:
    return f"t{thesis_id}" if thesis_id is not None else "none"
