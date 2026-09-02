from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class HostTelegram(TimestampMixin, Base):
    """Singleton host session. Parses vacancy channels for everyone.

    Candidates never connect their own Telegram — that stays a trust boundary.
    """

    __tablename__ = "host_telegram"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    api_id: Mapped[int | None] = mapped_column(Integer)
    api_hash: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    session_string: Mapped[str | None] = mapped_column(Text)
    phone_code_hash: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="disconnected", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime())
