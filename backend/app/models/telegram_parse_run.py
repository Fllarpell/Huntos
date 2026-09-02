from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TelegramParseRun(Base):
    __tablename__ = "telegram_parse_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
