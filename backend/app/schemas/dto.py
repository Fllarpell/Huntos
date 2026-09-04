from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.vacancy import HhPulse, NextStepKind, PipelineStage, ScoringStatus
from app.services.telegram import telegram_chat_url


class VacancyEventOut(BaseModel):
    id: int
    vacancy_id: int
    kind: NextStepKind
    starts_at: datetime
    ends_at: datetime | None = None
    label: str | None = None
    display_label: str
    google_event_id: str | None = None
    google_sync_error: str | None = None
    calendar_connected: bool = False


class VacancyEventWrite(BaseModel):
    kind: NextStepKind = NextStepKind.INTERVIEW
    starts_at: datetime
    ends_at: datetime | None = None
    label: str | None = None


class VacancyEventPatch(BaseModel):
    kind: NextStepKind | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    label: str | None = None


class VacancySearchRef(BaseModel):
    id: int
    name: str
    source: str


class CompanyContactHint(BaseModel):
    telegram_alias: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    label: str
    vacancy_id: int | None = None
    title: str | None = None
    card_count: int = 0


class CustomFieldDef(BaseModel):
    id: str
    name: str
    kind: str
    options: list[str] = Field(default_factory=list)
    scope: str = "hunt"


class CustomBit(BaseModel):
    id: str
    name: str
    kind: str
    value: str
    scope: str = "hunt"


class VacancyHuntRef(BaseModel):
    id: int
    name: str
    pinned: bool = False
    matched: bool = False


class VacancyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_id: str
    source_url: str | None
    title: str
    company: str | None
    company_inn: str | None = None
    company_icon: str | None
    grade: str | None
    work_format: str | None
    category: str | None
    industry: str | None
    location: str | None
    country: str | None
    region: str | None
    language: str | None
    salary_raw: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    description: str | None
    requirements: str | None
    tasks_html: str | None
    conditions_html: str | None
    important_info: str | None
    skills: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    published_at: datetime | None
    pipeline_stage: PipelineStage
    pipeline_position: int
    match_score: int | None
    scoring_status: ScoringStatus
    match_rationale: dict | None
    adaptation_advice: dict | None
    cover_letter: str | None
    notes: str | None
    telegram_alias: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    telegram_message: str | None = None
    extra_sources: list = Field(default_factory=list)
    custom_values: dict[str, str] = Field(default_factory=dict)
    custom_fields: list[CustomFieldDef] = Field(default_factory=list)
    custom_bits: list[CustomBit] = Field(default_factory=list)
    duplicate_of_id: int | None = None
    last_touch_at: datetime | None = None
    stage_entered_at: datetime | None = None
    outreach_at: datetime | None = None
    pinged_at: datetime | None = None
    hh_pulse: HhPulse | None = None
    hh_pulse_at: datetime | None = None
    next_step_at: datetime | None = None
    next_step_kind: NextStepKind | None = None
    google_event_id: str | None = None
    google_sync_error: str | None = None
    calendar_connected: bool = False
    collision_hint: str | None = None
    collision_peers: int = 0
    ping_due: bool = False
    silence_days: int | None = None
    dwell_days: int | None = None
    dwell_stale: bool = False
    events: list[VacancyEventOut] = Field(default_factory=list)
    company_contacts: list[CompanyContactHint] = Field(default_factory=list)
    hunts: list[VacancyHuntRef] = Field(default_factory=list)
    searches: list[VacancySearchRef] = Field(default_factory=list)
    stack_ids: list[str] = Field(default_factory=list)
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("company_icon", mode="before")
    @classmethod
    def _company_icon(cls, value: object) -> str | None:
        from app.services.company_icon import normalize_company_icon

        return normalize_company_icon(str(value) if value else None)

    @field_validator("extra_sources", mode="before")
    @classmethod
    def _extra_sources(cls, value: object) -> list:
        return value if isinstance(value, list) else []

    @model_validator(mode="after")
    def _compact_extra_sources(self):
        from app.services.extra_sources import compact_extra_sources

        self.extra_sources = compact_extra_sources(
            self.extra_sources, source=self.source, source_id=self.source_id
        )
        return self

    @field_validator("stack_ids", mode="before")
    @classmethod
    def _stack_ids(cls, value: object) -> list:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]

    @field_validator("searches", mode="before")
    @classmethod
    def _searches(cls, value: object) -> list:
        return value if isinstance(value, list) else []

    @field_validator("custom_values", mode="before")
    @classmethod
    def _custom_values(cls, value: object) -> dict:
        if not isinstance(value, dict):
            return {}
        return {str(k): str(v) for k, v in value.items() if v is not None and str(v).strip()}

    @field_validator("custom_fields", mode="before")
    @classmethod
    def _custom_fields(cls, value: object) -> list:
        return value if isinstance(value, list) else []

    @computed_field
    @property
    def telegram_url(self) -> str | None:
        return telegram_chat_url(self.telegram_alias)


class VacancyListOut(BaseModel):
    items: list[VacancyOut]
    total: int


class BulkStageUpdate(BaseModel):
    ids: list[int]
    stage: PipelineStage
    hunt_id: int | None = None


class StageUpdate(BaseModel):
    stage: PipelineStage
    position: int | None = None
    hunt_id: int | None = None


class NotesUpdate(BaseModel):
    notes: str = ""


class TelegramUpdate(BaseModel):
    telegram_alias: str = ""


class HhPulseUpdate(BaseModel):
    pulse: HhPulse | None = None


class ClipIn(BaseModel):
    url: str | None = None
    title: str | None = None
    company: str | None = None
    description: str | None = None
    salary_raw: str | None = None
    hunt_id: int | None = None


class ClipOut(BaseModel):
    created: bool
    merged: bool
    vacancy: VacancyOut


class VacancyWrite(BaseModel):
    title: str | None = None
    company: str | None = None
    company_inn: str | None = None
    grade: str | None = None
    work_format: str | None = None
    location: str | None = None
    country: str | None = None
    language: str | None = None
    salary_raw: str | None = None
    description: str | None = None
    source_url: str | None = None
    telegram_alias: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
    skills: list[str] | None = None
    custom_values: dict[str, str] | None = None
    card_fields: list[CustomFieldDef] | None = None
    hunt_id: int | None = None
    pipeline_stage: PipelineStage | None = None
    next_step_at: datetime | None = None
    next_step_kind: NextStepKind | None = None


class ReorderItem(BaseModel):
    id: int
    stage: PipelineStage
    position: int


class PipelineColumn(BaseModel):
    stage: PipelineStage
    items: list[VacancyOut]


class CollisionItem(BaseModel):
    id: int
    event_id: int | None = None
    company: str | None
    title: str
    label: str | None = None
    next_step_at: datetime
    ends_at: datetime | None = None
    next_step_kind: NextStepKind | None = None
    match_score: int | None = None
    pipeline_stage: PipelineStage


class CollisionDay(BaseModel):
    date: str
    label: str
    hint: str
    press_id: int
    items: list[CollisionItem]


class CollisionOut(BaseModel):
    days: list[CollisionDay]
    upcoming: list[CollisionItem]


class CalendarPingSlot(BaseModel):
    id: int
    thesis_id: int | None = None
    label: str
    card_count: int
    ping_at: datetime | None = None
    vacancy_ids: list[int] = Field(default_factory=list)


class CalendarBoardOut(BaseModel):
    calendar_connected: bool = False
    calendar_ready: bool = False
    collisions: list[CollisionDay] = Field(default_factory=list)
    meetings: list[CollisionItem] = Field(default_factory=list)
    ping_slots: list[CalendarPingSlot] = Field(default_factory=list)


class ScraperRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scraper_config_id: int | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    found_count: int
    new_count: int
    updated_count: int
    error: str | None


class ScraperConfigIn(BaseModel):
    name: str = ""
    source: str = "hirehi"
    enabled: bool = True
    listing_url: str | None = None
    query_params: dict = Field(default_factory=dict)
    interval_minutes: int = 60
    max_pages: int = 5


class ScraperConfigOut(ScraperConfigIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_run: ScraperRunOut | None = None
    next_run_at: datetime | None = None
    from_pool: bool = False


class CareerBoardOut(BaseModel):
    slug: str
    name: str
    listing_url: str
    hint: str = ""
    logo_url: str = ""


class DonorCrawlOut(BaseModel):
    query_key: str
    source: str
    name: str
    listing_url: str | None = None
    query_params: dict = Field(default_factory=dict)
    last_fetched_at: datetime | None = None
    last_status: str
    last_error: str | None = None
    found_count: int = 0
    queue_status: str | None = None
    subscriber_count: int = 0
    subscribers: list[str] = Field(default_factory=list)
    host_subscribed: bool = False


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str | None
    resume_text: str | None
    resume_filename: str | None
    llm_provider: str
    llm_model: str
    openai_api_key_set: bool = False
    ollama_base_url: str
    target_roles: list = Field(default_factory=list)
    target_grades: list = Field(default_factory=list)
    target_formats: list = Field(default_factory=list)
    custom_fields: list[CustomFieldDef] = Field(default_factory=list)
    google_connected: bool = False
    google_email: str | None = None
    google_client_id_set: bool = False
    google_redirect_uri: str | None = None
    google_calendar_ready: bool = False
    google_needs_reconnect: bool = False
    google_calendar_error: str | None = None

    @field_validator("custom_fields", mode="before")
    @classmethod
    def _profile_fields(cls, value: object) -> list:
        return value if isinstance(value, list) else []


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    resume_text: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str | None = None
    target_roles: list | None = None
    target_grades: list | None = None
    target_formats: list | None = None
    custom_fields: list[CustomFieldDef] | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
