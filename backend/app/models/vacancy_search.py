from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VacancySearch(Base):
    """Every saved search that collected this vacancy (not only the last one)."""

    __tablename__ = "vacancy_searches"

    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), primary_key=True)
    scraper_config_id: Mapped[int] = mapped_column(
        ForeignKey("scraper_configs.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
