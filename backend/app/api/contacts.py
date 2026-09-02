from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.contact import SavedContact
from app.models.user import User
from app.services.contacts import filter_pool, load_all_pools, load_pool
from app.services.deps import get_current_user, get_scope_user
from app.services.telegram import normalize_telegram_alias
from app.services.vacancy_write import normalize_email, normalize_inn, normalize_phone

router = APIRouter(prefix="/api", tags=["contacts"])


class ContactCardOut(BaseModel):
    id: int
    title: str
    company: str | None
    company_inn: str | None = None
    pipeline_stage: str


class ContactCompanyOut(BaseModel):
    name: str | None
    inn: str | None = None
    label: str
    org_key: str | None = None
    company_icon: str | None = None
    card_count: int = 0
    saved: bool = False


class ContactOut(BaseModel):
    id: str
    telegram_alias: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    label: str
    companies: list[ContactCompanyOut] = Field(default_factory=list)
    cards: list[ContactCardOut] = Field(default_factory=list)
    saved_ids: list[int] = Field(default_factory=list)
    card_count: int = 0
    owner_id: int | None = None
    owner_email: str | None = None


class ContactWrite(BaseModel):
    company: str | None = None
    company_inn: str | None = None
    telegram_alias: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    note: str | None = None


def _person_out(row: dict) -> ContactOut:
    return ContactOut.model_validate(
        {
            **row,
            "cards": row.get("cards") or [],
            "companies": row.get("companies") or [],
        }
    )


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    q: str | None = None,
    pool: str | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
    scope: User = Depends(get_scope_user),
) -> list[ContactOut]:
    if (pool or "").strip() == "all":
        if not actor.is_host:
            raise HTTPException(403, "Общий пул контактов видит только хост")
        people = filter_pool(await load_all_pools(session), q)
    else:
        people = filter_pool(await load_pool(session, scope.id), q)
    return [_person_out(row) for row in people]


@router.post("/contacts", response_model=ContactOut)
async def create_contact(
    payload: ContactWrite,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> ContactOut:
    telegram = normalize_telegram_alias(payload.telegram_alias)
    email = normalize_email(payload.contact_email)
    phone = normalize_phone(payload.contact_phone)
    if not telegram and not email and not phone:
        raise HTTPException(400, "Нужен Telegram, email или телефон")
    now = datetime.now(UTC).replace(tzinfo=None)
    row = SavedContact(
        user_id=user.id,
        company=(payload.company or "").strip() or None,
        company_inn=normalize_inn(payload.company_inn),
        telegram_alias=telegram,
        contact_email=email,
        contact_phone=phone,
        note=(payload.note or "").strip() or None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    people = await load_pool(session, user.id)
    match = next((p for p in people if row.id in p["saved_ids"]), None)
    if match is None:
        raise HTTPException(500, "Контакт не собрался")
    return _person_out(match)


@router.delete("/contacts/saved/{contact_id}")
async def delete_saved_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_scope_user),
) -> dict:
    row = await session.get(SavedContact, contact_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Контакт не найден")
    await session.delete(row)
    await session.commit()
    return {"ok": True}
