from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class UserProfile(TimestampMixin, Base):
    """Per-user resume + LLM credentials. Never shared across accounts."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    display_name: Mapped[str | None] = mapped_column(String(128))
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_filename: Mapped[str | None] = mapped_column(String(255))

    llm_provider: Mapped[str] = mapped_column(String(32), default="openai", nullable=False)
    llm_model: Mapped[str] = mapped_column(String(64), default="gpt-4o-mini", nullable=False)
    openai_api_key: Mapped[str | None] = mapped_column(Text)
    ollama_base_url: Mapped[str] = mapped_column(
        String(255),
        default="http://127.0.0.1:11434",
        nullable=False,
    )

    target_roles: Mapped[list] = mapped_column(JSON, default=list)
    target_grades: Mapped[list] = mapped_column(JSON, default=list)
    target_formats: Mapped[list] = mapped_column(JSON, default=list)
    custom_fields: Mapped[list] = mapped_column(JSON, default=list)
    active_hunt_id: Mapped[int | None] = mapped_column(
        ForeignKey("hunt_theses.id", ondelete="SET NULL"),
        index=True,
    )

    google_client_id: Mapped[str | None] = mapped_column(Text)
    google_client_secret: Mapped[str | None] = mapped_column(Text)
    google_refresh_token: Mapped[str | None] = mapped_column(Text)
    google_access_token: Mapped[str | None] = mapped_column(Text)
    google_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime())
    google_email: Mapped[str | None] = mapped_column(String(255))
    google_calendar_id: Mapped[str | None] = mapped_column(String(256))
    google_sync_token: Mapped[str | None] = mapped_column(Text)
    google_calendar_error: Mapped[str | None] = mapped_column(Text)
    google_pulled_at: Mapped[datetime | None] = mapped_column(DateTime())
