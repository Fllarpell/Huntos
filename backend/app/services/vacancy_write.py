from __future__ import annotations

import re

from datetime import UTC, datetime

from sqlalchemy.orm.attributes import flag_modified

from app.models.vacancy import HhPulse, NextStepKind, PipelineStage, Vacancy
from app.schemas.dto import VacancyWrite
from app.services.custom_fields import MAX_CARD_FIELDS, normalize_defs, normalize_values
from app.services.scraper.salary import parse_salary
from app.services.telegram import normalize_telegram_alias
from app.services.wip import enter_stage, touch
from app.services.vacancy_events import promote_for_step


def normalize_email(raw: str | None) -> str | None:
    text = (raw or "").strip().lower()
    return text[:255] or None


def normalize_phone(raw: str | None) -> str | None:
    text = re.sub(r"[^\d+()\-\s]", "", (raw or "").strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text[:64] or None


def normalize_inn(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) in {10, 12}:
        return digits
    return None


_ANON_NAMES = {"nda", "нда"}


def company_key(name: str | None) -> str:
    return (name or "").strip().lower()


def is_anon_company_name(name: str | None) -> bool:
    compact = re.sub(r"[.\s]+", "", (name or "").strip().lower())
    return not compact or compact in _ANON_NAMES

_HAS_SCHEME = re.compile(r"^https?://", re.IGNORECASE)


def normalize_http_url(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if not _HAS_SCHEME.match(text):
        text = f"https://{text}"
    return text[:512]


def apply_vacancy_write(vacancy: Vacancy, payload: VacancyWrite) -> None:
    data = payload.model_dump(exclude_unset=True)
    changed = set(data)
    if "telegram_alias" in data:
        vacancy.telegram_alias = normalize_telegram_alias(data.pop("telegram_alias") or "")
    if "contact_email" in data:
        vacancy.contact_email = normalize_email(data.pop("contact_email") or "")
    if "contact_phone" in data:
        vacancy.contact_phone = normalize_phone(data.pop("contact_phone") or "")
    if "company_inn" in data:
        digits = re.sub(r"\D", "", data.pop("company_inn") or "")
        if not digits:
            vacancy.company_inn = None
        elif len(digits) in {10, 12}:
            vacancy.company_inn = digits
    if "source_url" in data:
        vacancy.source_url = normalize_http_url(data.pop("source_url"))
    if "skills" in data:
        vacancy.skills = [str(s).strip() for s in (data.pop("skills") or []) if str(s).strip()]
    if "custom_values" in data:
        vacancy.custom_values = normalize_values(data.pop("custom_values"))
        flag_modified(vacancy, "custom_values")
    if "card_fields" in data:
        vacancy.card_fields = normalize_defs(data.pop("card_fields"), limit=MAX_CARD_FIELDS)
        flag_modified(vacancy, "card_fields")
    data.pop("hunt_id", None)
    if "salary_raw" in data:
        raw = data.pop("salary_raw")
        vacancy.salary_raw = (raw or "").strip() or None
        lo, hi, currency = parse_salary(vacancy.salary_raw)
        vacancy.salary_min = lo
        vacancy.salary_max = hi
        if currency:
            vacancy.salary_currency = currency
        elif vacancy.salary_raw is None:
            vacancy.salary_min = None
            vacancy.salary_max = None
    if "title" in data:
        vacancy.title = (data.pop("title") or "").strip() or "Без названия"
    if "next_step_at" in data or "next_step_kind" in data:
        step_at = data.pop("next_step_at", vacancy.next_step_at)
        step_kind = data.pop("next_step_kind", vacancy.next_step_kind)
        if not step_at:
            vacancy.next_step_at = None
            vacancy.next_step_kind = None
        else:
            vacancy.next_step_at = step_at
            vacancy.next_step_kind = step_kind or NextStepKind.INTERVIEW
            promote_for_step(vacancy, vacancy.next_step_kind)
    if "pipeline_stage" in data:
        enter_stage(vacancy, data.pop("pipeline_stage"))
    for key, value in data.items():
        if key in {"salary_min", "salary_max", "hh_pulse", "hh_pulse_at"}:
            continue
        if hasattr(vacancy, key):
            if isinstance(value, str):
                value = value.strip() or None
            setattr(vacancy, key, value)
    if changed & {"skills", "grade", "work_format", "language"}:
        tags: list[str] = []
        for item in (vacancy.grade, vacancy.work_format, vacancy.language, *(vacancy.skills or [])):
            if item and item not in tags:
                tags.append(item)
        vacancy.tags = tags[:24]


def apply_wrote(vacancy: Vacancy) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    enter_stage(vacancy, PipelineStage.WAITING)
    vacancy.outreach_at = vacancy.outreach_at or now
    touch(vacancy)


def apply_pinged(vacancy: Vacancy) -> None:
    vacancy.pinged_at = datetime.now(UTC).replace(tzinfo=None)
    touch(vacancy)


def apply_hh_pulse(vacancy: Vacancy, pulse: HhPulse | None) -> None:
    """Platform signal. Does not move the column — that would be Talantix lock-in."""
    vacancy.hh_pulse = pulse
    if pulse is None:
        vacancy.hh_pulse_at = None
        return
    vacancy.hh_pulse_at = datetime.now(UTC).replace(tzinfo=None)
    touch(vacancy)
