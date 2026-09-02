from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScraperRun(Base):
    """Audit log for cron / manual scraper runs. Not part of the core 3 tables,
    but needed to debug bans, empty pages, and scoring backlog.
    """

    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scraper_config_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scraper_configs.id"),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
