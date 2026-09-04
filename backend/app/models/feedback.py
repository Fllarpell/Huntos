from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class FeedbackNote(TimestampMixin, Base):
    __tablename__ = "feedback_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[str | None] = mapped_column(String(256))
    contact_name: Mapped[str | None] = mapped_column(String(128))
    reply_to: Mapped[str | None] = mapped_column(String(256))
