from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class DonorQueryCache(TimestampMixin, Base):
    """One unique hh/HireHi search. The host worker fetches it; users subscribe via scraper_configs."""

    __tablename__ = "donor_query_caches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    query_params: Mapped[dict] = mapped_column(JSON, default=dict)
    listing_url: Mapped[str | None] = mapped_column(Text)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime())
    last_status: Mapped[str] = mapped_column(String(16), default="idle", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DonorListing(TimestampMixin, Base):
    """Canonical vacancy from a donor site, then copied into each subscriber's inbox."""

    __tablename__ = "donor_listings"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_donor_listing_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime())


class DonorQueryListing(Base):
    __tablename__ = "donor_query_listings"
    __table_args__ = (UniqueConstraint("query_id", "listing_id", name="uq_donor_query_listing"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("donor_query_caches.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("donor_listings.id", ondelete="CASCADE"), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
