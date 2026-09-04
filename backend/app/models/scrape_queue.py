from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class ScrapeQueueItem(Base):
    """Host-side crawl jobs. Unique pending/running query_key — N users share one fetch."""

    __tablename__ = "scrape_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    force: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requested_by_config_id: Mapped[int | None] = mapped_column(Integer)
    requested_by_user_id: Mapped[int | None] = mapped_column(Integer)
    requested_config_ids: Mapped[list] = mapped_column(JSON, default=list)
    queued_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime())
    error: Mapped[str | None] = mapped_column(Text)
