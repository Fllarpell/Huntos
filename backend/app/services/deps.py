from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.scraper_config import ScraperConfig
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_event import VacancyEvent
from app.services.auth import user_from_request

AS_USER_HEADER = "X-Hunt-As"


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await user_from_request(session, request)
    if user is None:
        raise HTTPException(401, "Нужно войти")
    return user


def can_view_others(user: User) -> bool:
    return bool(user.is_host or user.can_observe)


async def get_scope_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
    x_hunt_as: str | None = Header(default=None, alias=AS_USER_HEADER),
) -> User:
    raw = (x_hunt_as or request.query_params.get("as_user") or "").strip()
    if not raw:
        return actor
    if not can_view_others(actor):
        raise HTTPException(403, "Чужие данные недоступны")
    try:
        uid = int(raw)
    except ValueError as exc:
        raise HTTPException(400, "Некорректный пользователь") from exc
    if uid == actor.id:
        return actor
    target = await session.get(User, uid)
    if target is None:
        raise HTTPException(404, "Пользователь не найден")
    return target


async def vacancy_for_user(session: AsyncSession, user: User, vacancy_id: int) -> Vacancy:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.user_id != user.id:
        raise HTTPException(404, "Vacancy not found")
    return vacancy


async def event_for_user(session: AsyncSession, user: User, event_id: int) -> tuple[VacancyEvent, Vacancy]:
    event = await session.get(VacancyEvent, event_id)
    if event is None or event.user_id != user.id:
        raise HTTPException(404, "Событие не найдено")
    vacancy = await vacancy_for_user(session, user, event.vacancy_id)
    return event, vacancy


async def config_for_user(session: AsyncSession, user: User, config_id: int) -> ScraperConfig:
    config = await session.get(ScraperConfig, config_id)
    if config is None or config.user_id != user.id:
        raise HTTPException(404, "Config not found")
    return config


async def require_host(user: User = Depends(get_current_user)) -> User:
    if not user.is_host:
        raise HTTPException(403, "Это может только хост")
    return user


def owned_vacancies(user: User):
    return select(Vacancy).where(Vacancy.user_id == user.id)
