from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class HuntThesis(TimestampMixin, Base):
    """A falsifiable bet on a market segment. Vacancies are samples, not a to-do list."""

    __tablename__ = "hunt_theses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role_query: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    grades: Mapped[list] = mapped_column(JSON, default=list)
    formats: Mapped[list] = mapped_column(JSON, default=list)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    no_nda: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    min_sample: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    min_median_match: Mapped[int] = mapped_column(Integer, default=55, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_fields: Mapped[list] = mapped_column(JSON, default=list)
    last_verdict: Mapped[str | None] = mapped_column(String(16))
    last_reason: Mapped[str | None] = mapped_column(String(512))
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime())
