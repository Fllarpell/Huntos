from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import SavedContact
from app.models.user import User
from app.models.vacancy import PipelineStage, Vacancy
from app.services.company_icon import icon_brand_key, normalize_company_icon, pick_consensus_icon
from app.services.telegram import normalize_telegram_alias
from app.services.vacancy_write import company_key, is_anon_company_name, normalize_email, normalize_inn, normalize_phone

_DIGITS = re.compile(r"\D+")


def org_label(name: str | None, inn: str | None) -> str:
    display = (name or "").strip() or "без компании"
    inn_n = normalize_inn(inn)
    if inn_n:
        return f"{display} · ИНН {inn_n}"
    return display


def org_key(
    name: str | None,
    inn: str | None,
    *,
    vacancy_id: int | None = None,
    saved_id: int | None = None,
) -> str:
    inn_n = normalize_inn(inn)
    if inn_n:
        return f"inn:{inn_n}"
    if is_anon_company_name(name):
        if vacancy_id is not None:
            return f"anon:v:{vacancy_id}"
        if saved_id is not None:
            return f"anon:s:{saved_id}"
        return "anon"
    named = company_key(name)
    return f"name:{named}" if named else "anon"


def hintable_org_key(name: str | None, inn: str | None) -> str | None:
    inn_n = normalize_inn(inn)
    if inn_n:
        return f"inn:{inn_n}"
    if is_anon_company_name(name):
        return None
    named = company_key(name)
    return f"name:{named}" if named else None


def _icon_maps(vacancies: list[Vacancy]) -> tuple[dict[str, str], dict[str, str]]:
    by_inn: dict[str, list[str]] = defaultdict(list)
    by_name: dict[str, list[str]] = defaultdict(list)
    for row in vacancies:
        icon = normalize_company_icon(row.company_icon, page_url=row.source_url)
        if not icon:
            continue
        inn = normalize_inn(row.company_inn)
        if inn:
            by_inn[inn].append(icon)
        brand = icon_brand_key(row.company)
        if brand:
            by_name[brand].append(icon)

    def _winner(urls: list[str]) -> str | None:
        return pick_consensus_icon(urls)[0]

    return (
        {key: icon for key, urls in by_inn.items() if (icon := _winner(urls))},
        {key: icon for key, urls in by_name.items() if (icon := _winner(urls))},
    )


def _org_icon(
    name: str | None,
    inn: str | None,
    *,
    own: str | None = None,
    by_inn: dict[str, str],
    by_name: dict[str, str],
) -> str | None:
    found = normalize_company_icon(own)
    if found:
        return found
    inn_n = normalize_inn(inn)
    if inn_n and inn_n in by_inn:
        return by_inn[inn_n]
    if is_anon_company_name(name):
        return None
    brand = icon_brand_key(name)
    return by_name.get(brand) if brand else None


def phone_key(raw: str | None) -> str | None:
    digits = _DIGITS.sub("", raw or "")
    if len(digits) >= 10:
        return digits[-10:]
    return digits or None


def _tokens(telegram: str | None, email: str | None, phone: str | None) -> list[str]:
    out: list[str] = []
    alias = normalize_telegram_alias(telegram)
    if alias:
        out.append(f"tg:{alias.lower()}")
    mail = normalize_email(email)
    if mail:
        out.append(f"em:{mail}")
    phone_id = phone_key(phone)
    if phone_id:
        out.append(f"ph:{phone_id}")
    return out


class _UF:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _has_contact(telegram: str | None, email: str | None, phone: str | None) -> bool:
    return bool(_tokens(telegram, email, phone))


def _pack_person(
    members: list[dict],
    *,
    by_inn: dict[str, str],
    by_name: dict[str, str],
) -> dict:
    telegram = next((m["telegram_alias"] for m in members if m.get("telegram_alias")), None)
    email = next((m["contact_email"] for m in members if m.get("contact_email")), None)
    phone = next((m["contact_phone"] for m in members if m.get("contact_phone")), None)
    cards: list[dict] = []
    saved_ids: list[int] = []
    companies: dict[str, dict] = {}
    updated = None
    for m in members:
        inn = normalize_inn(m.get("company_inn"))
        if m["kind"] == "vacancy":
            cards.append(
                {
                    "id": m["vacancy_id"],
                    "title": m["title"],
                    "company": m["company"],
                    "company_inn": inn,
                    "pipeline_stage": m["pipeline_stage"],
                }
            )
        else:
            saved_ids.append(m["saved_id"])
        key = org_key(
            m["company"],
            inn,
            vacancy_id=m.get("vacancy_id"),
            saved_id=m.get("saved_id"),
        )
        slot = companies.setdefault(
            key,
            {
                "org_key": key,
                "name": m["company"],
                "inn": inn,
                "label": org_label(m["company"], inn),
                "company_icon": None,
                "card_count": 0,
                "saved": False,
            },
        )
        if is_anon_company_name(slot["name"]) and not is_anon_company_name(m["company"]):
            slot["name"] = m["company"]
        slot["inn"] = inn or slot["inn"]
        slot["label"] = org_label(slot["name"], slot["inn"])
        icon = _org_icon(
            slot["name"],
            slot["inn"],
            own=m.get("company_icon"),
            by_inn=by_inn,
            by_name=by_name,
        )
        if icon:
            slot["company_icon"] = icon
        if m["kind"] == "vacancy":
            slot["card_count"] += 1
        else:
            slot["saved"] = True
        stamp = m.get("updated_at")
        if stamp and (updated is None or stamp > updated):
            updated = stamp
    cards.sort(key=lambda row: (row["company"] or "", row["company_inn"] or "", row["title"] or ""))
    company_list = sorted(companies.values(), key=lambda row: (row["label"] or "яяя").lower())
    label = (
        f"@{telegram}" if telegram else None
    ) or email or phone or "без идентификатора"
    return {
        "id": "|".join(_tokens(telegram, email, phone)) or members[0]["node"],
        "telegram_alias": telegram,
        "contact_email": email,
        "contact_phone": phone,
        "label": label,
        "companies": company_list,
        "cards": cards,
        "saved_ids": saved_ids,
        "card_count": len(cards),
        "updated_at": updated,
    }


async def load_pool(session: AsyncSession, user_id: int) -> list[dict]:
    vacancies = (
        await session.execute(
            select(Vacancy).where(
                Vacancy.user_id == user_id,
                Vacancy.duplicate_of_id.is_(None),
                Vacancy.pipeline_stage != PipelineStage.TRASH,
            )
        )
    ).scalars().all()
    saved = (
        await session.execute(select(SavedContact).where(SavedContact.user_id == user_id))
    ).scalars().all()

    by_inn, by_name = _icon_maps(list(vacancies))

    uf = _UF()
    members: dict[str, dict] = {}

    for row in vacancies:
        if not _has_contact(row.telegram_alias, row.contact_email, row.contact_phone):
            continue
        node = f"v:{row.id}"
        members[node] = {
            "kind": "vacancy",
            "node": node,
            "vacancy_id": row.id,
            "title": row.title,
            "company": row.company,
            "company_inn": row.company_inn,
            "company_icon": row.company_icon,
            "pipeline_stage": row.pipeline_stage.value if hasattr(row.pipeline_stage, "value") else row.pipeline_stage,
            "telegram_alias": normalize_telegram_alias(row.telegram_alias),
            "contact_email": normalize_email(row.contact_email),
            "contact_phone": normalize_phone(row.contact_phone) or (row.contact_phone or "").strip() or None,
            "updated_at": row.updated_at,
        }
        toks = _tokens(row.telegram_alias, row.contact_email, row.contact_phone)
        uf.union(node, toks[0])
        for tok in toks[1:]:
            uf.union(node, tok)

    for row in saved:
        if not _has_contact(row.telegram_alias, row.contact_email, row.contact_phone):
            continue
        node = f"s:{row.id}"
        members[node] = {
            "kind": "saved",
            "node": node,
            "saved_id": row.id,
            "title": None,
            "company": row.company,
            "company_inn": row.company_inn,
            "pipeline_stage": None,
            "telegram_alias": normalize_telegram_alias(row.telegram_alias),
            "contact_email": normalize_email(row.contact_email),
            "contact_phone": normalize_phone(row.contact_phone) or (row.contact_phone or "").strip() or None,
            "updated_at": row.updated_at,
        }
        toks = _tokens(row.telegram_alias, row.contact_email, row.contact_phone)
        uf.union(node, toks[0])
        for tok in toks[1:]:
            uf.union(node, tok)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for node, payload in members.items():
        grouped[uf.find(node)].append(payload)

    people = [_pack_person(items, by_inn=by_inn, by_name=by_name) for items in grouped.values()]
    people.sort(
        key=lambda row: (
            -(row["card_count"]),
            (row["companies"][0]["label"] or "").lower() if row["companies"] else "",
            row["label"].lower(),
        )
    )
    return people


async def load_all_pools(session: AsyncSession) -> list[dict]:
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    people: list[dict] = []
    for user in users:
        for person in await load_pool(session, user.id):
            people.append(
                {
                    **person,
                    "id": f"{user.id}:{person['id']}",
                    "owner_id": user.id,
                    "owner_email": user.email,
                }
            )
    people.sort(
        key=lambda row: (
            (row.get("owner_email") or "").lower(),
            -(row["card_count"]),
            row["label"].lower(),
        )
    )
    return people


def filter_pool(people: list[dict], q: str | None) -> list[dict]:
    raw = (q or "").strip().lower().lstrip("@")
    if not raw:
        return people
    out = []
    for person in people:
        hay = " ".join(
            [
                person["label"] or "",
                person["telegram_alias"] or "",
                person["contact_email"] or "",
                person["contact_phone"] or "",
                *[c["name"] or "" for c in person["companies"]],
                *[c.get("inn") or "" for c in person["companies"]],
                *[c.get("label") or "" for c in person["companies"]],
                *[c["title"] or "" for c in person["cards"]],
                *[c.get("company_inn") or "" for c in person["cards"]],
                person.get("owner_email") or "",
            ]
        ).lower()
        if raw in hay:
            out.append(person)
    return out


def company_hints(people: list[dict], vacancy: Vacancy) -> list[dict]:
    key = hintable_org_key(vacancy.company, vacancy.company_inn)
    if not key:
        return []
    mine = set(_tokens(vacancy.telegram_alias, vacancy.contact_email, vacancy.contact_phone))
    hints = []
    for person in people:
        companies = {c.get("org_key") for c in person["companies"] if c.get("org_key")}
        if key not in companies:
            continue
        other = [card for card in person["cards"] if card["id"] != vacancy.id]
        saved = bool(person["saved_ids"])
        if not other and not saved:
            continue
        theirs = set(_tokens(person["telegram_alias"], person["contact_email"], person["contact_phone"]))
        if theirs and theirs <= mine:
            continue
        hints.append(
            {
                "telegram_alias": person["telegram_alias"],
                "contact_email": person["contact_email"],
                "contact_phone": person["contact_phone"],
                "label": person["label"],
                "vacancy_id": other[0]["id"] if other else None,
                "title": other[0]["title"] if other else None,
                "card_count": len(other),
            }
        )
    return hints[:8]


async def hints_for_vacancy(session: AsyncSession, user_id: int, vacancy: Vacancy) -> list[dict]:
    return company_hints(await load_pool(session, user_id), vacancy)
