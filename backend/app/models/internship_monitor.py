from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InternshipMonitor(Base):
    """Latest daily check of a catalog program's public landing page."""

    __tablename__ = "internship_monitors"

    program_slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    live_status: Mapped[str] = mapped_column(String(16), nullable=False)
    signal: Mapped[str | None] = mapped_column(String(255))
    check_error: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
