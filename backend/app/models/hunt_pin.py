from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class HuntPin(TimestampMixin, Base):
    """Explicit share of a vacancy into a hunt. Match by thesis still includes without a pin."""

    __tablename__ = "hunt_pins"
    __table_args__ = (UniqueConstraint("hunt_id", "vacancy_id", name="uq_hunt_pin"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunt_theses.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
