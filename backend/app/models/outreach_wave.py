from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class OutreachWave(TimestampMixin, Base):
    """A pack of touches sent under a thesis. Not a WIP slot."""

    __tablename__ = "outreach_waves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thesis_id: Mapped[int] = mapped_column(ForeignKey("hunt_theses.id", ondelete="CASCADE"), index=True)
    vacancy_ids: Mapped[list] = mapped_column(JSON, default=list)
    wrote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    drafted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime())
