from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class ScraperConfig(TimestampMixin, Base):
    """One saved search. Query params are sent to the donor's JSON API as-is.

    HireHi example (matches the listing URL you sent):
      source = "hirehi"
      listing_url = "https://hirehi.ru/vacancies/development?format=удалённо&search=ML"
      query_params = {
        "category": "development",
        "search": "ML",
        "format": ["удалённо"],
        "sort": "date",
        "level": [],
        "subcategory": []
      }
    """

    __tablename__ = "scraper_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="hirehi")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    listing_url: Mapped[str | None] = mapped_column(Text)
    query_params: Mapped[dict] = mapped_column(JSON, default=dict)
    # Same key = same donor fetch. Users subscribe; the host worker scrapes once.
    query_key: Mapped[str | None] = mapped_column(String(64), index=True)

    # How often this user wants a refresh. Actual crawl is max(global min, min(subscribers)).
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
