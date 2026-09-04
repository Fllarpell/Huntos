import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models.mixins import TimestampMixin


class PipelineStage(str, enum.Enum):
    INBOX = "inbox"
    TO_APPLY = "to_apply"
    WAITING = "waiting"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    TRASH = "trash"


class ScoringStatus(str, enum.Enum):
    PENDING = "pending"
    SCORED = "scored"
    ERROR = "error"
    SKIPPED = "skipped"


class NextStepKind(str, enum.Enum):
    SCREENING = "screening"
    INTERVIEW = "interview"
    ASSIGNMENT = "assignment"
    OFFER_DEADLINE = "offer_deadline"


class HhPulse(str, enum.Enum):
    INVITED = "invited"
    DISCARDED = "discarded"


class Vacancy(TimestampMixin, Base):
    """Normalized vacancy. Dedup key: (user_id, source, source_id)."""

    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "source_id", name="uq_vacancy_user_source_id"),
        Index("ix_vacancies_inbox", "user_id", "pipeline_stage", "match_score"),
        Index("ix_vacancies_published", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False, default="hirehi")
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512))

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    company_inn: Mapped[str | None] = mapped_column(String(16))
    company_icon: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(String(32))  # intern..head
    work_format: Mapped[str | None] = mapped_column(String(64))  # удалённо / офис / гибрид
    category: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(64))

    salary_raw: Mapped[str | None] = mapped_column(String(128))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(8), default="RUB")

    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    tasks_html: Mapped[str | None] = mapped_column(Text)
    conditions_html: Mapped[str | None] = mapped_column(Text)
    important_info: Mapped[str | None] = mapped_column(Text)

    skills: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    stack_ids: Mapped[list] = mapped_column(JSON, default=list)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    published_at: Mapped[datetime | None] = mapped_column(DateTime())

    pipeline_stage: Mapped[PipelineStage] = mapped_column(
        Enum(PipelineStage, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=PipelineStage.INBOX,
        nullable=False,
    )
    pipeline_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    match_score: Mapped[int | None] = mapped_column(Integer)  # 0..100
    scoring_status: Mapped[ScoringStatus] = mapped_column(
        Enum(ScoringStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=ScoringStatus.PENDING,
        nullable=False,
    )
    match_rationale: Mapped[dict | None] = mapped_column(JSON)
    adaptation_advice: Mapped[dict | None] = mapped_column(JSON)
    cover_letter: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    telegram_alias: Mapped[str | None] = mapped_column(String(128))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    telegram_message: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(String(190), index=True)
    extra_sources: Mapped[list] = mapped_column(JSON, default=list)
    custom_values: Mapped[dict] = mapped_column(JSON, default=dict)
    card_fields: Mapped[list] = mapped_column(JSON, default=list)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="SET NULL"), index=True)
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime())
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime())
    outreach_at: Mapped[datetime | None] = mapped_column(DateTime())
    pinged_at: Mapped[datetime | None] = mapped_column(DateTime())
    hh_pulse: Mapped[HhPulse | None] = mapped_column(
        Enum(HhPulse, native_enum=False, values_callable=lambda x: [e.value for e in x]),
    )
    hh_pulse_at: Mapped[datetime | None] = mapped_column(DateTime())
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime())
    next_step_kind: Mapped[NextStepKind | None] = mapped_column(
        Enum(NextStepKind, native_enum=False, values_callable=lambda x: [e.value for e in x]),
    )
    google_event_id: Mapped[str | None] = mapped_column(String(128))
    google_sync_error: Mapped[str | None] = mapped_column(Text)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime())
    scraper_config_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scraper_configs.id", ondelete="SET NULL"),
    )
