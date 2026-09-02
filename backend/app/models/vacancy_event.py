from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin
from app.models.vacancy import NextStepKind


class VacancyEvent(TimestampMixin, Base):
    """One calendar step on a vacancy. Same company can have screening + several interviews."""

    __tablename__ = "vacancy_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    kind: Mapped[NextStepKind] = mapped_column(
        Enum(NextStepKind, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=NextStepKind.INTERVIEW,
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime())
    label: Mapped[str | None] = mapped_column(String(64))
    google_event_id: Mapped[str | None] = mapped_column(String(128))
    google_sync_error: Mapped[str | None] = mapped_column(Text)
