from __future__ import annotations

import re
from uuid import uuid4

MAX_HUNT_FIELDS = 8
MAX_CARD_FIELDS = 8
MAX_OPTIONS = 12
KINDS = ("text", "number", "date", "select", "check")
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,24}$")
CHECK_TRUE = {"1", "true", "да", "yes", "on"}


def new_field_id() -> str:
    return uuid4().hex[:10]


def normalize_defs(raw: object, *, strict: bool = True, limit: int = MAX_HUNT_FIELDS) -> list[dict]:
    items = raw if isinstance(raw, list) else []
    if len(items) > limit:
        if strict:
            raise ValueError(f"Не больше {limit} полей")
        items = items[:limit]
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:40]
        kind = str(item.get("kind") or "text").strip()
        if kind == "bool":
            kind = "check"
        if not name or kind not in KINDS:
            if strict:
                raise ValueError("У поля нужны имя и тип: текст, число, дата, выбор или чекбокс")
            continue
        fid = str(item.get("id") or "").strip()
        if not ID_RE.match(fid) or fid in seen:
            fid = new_field_id()
        seen.add(fid)
        rec: dict = {"id": fid, "name": name, "kind": kind}
        if kind == "select":
            opts = item.get("options") or []
            if isinstance(opts, str):
                opts = [part.strip() for part in opts.split(",")]
            cleaned: list[str] = []
            for option in opts:
                text = str(option).strip()[:40]
                if text and text not in cleaned:
                    cleaned.append(text)
            if len(cleaned) < 2:
                if strict:
                    raise ValueError(f"«{name}»: для выбора нужно хотя бы два варианта")
                continue
            rec["options"] = cleaned[:MAX_OPTIONS]
        out.append(rec)
    return out


def normalize_values(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in list(raw.items())[:24]:
        fid = str(key).strip()
        if not ID_RE.match(fid) or value is None:
            continue
        if isinstance(value, bool):
            out[fid] = "1" if value else "0"
            continue
        text = str(value).strip()[:500]
        if text:
            out[fid] = text
    return out


def _as_dict(item: object) -> dict:
    if isinstance(item, dict):
        return dict(item)
    dump = getattr(item, "model_dump", None)
    return dump() if callable(dump) else {}


def with_scope(defs: list, scope: str) -> list[dict]:
    return [{**_as_dict(item), "scope": scope} for item in defs]


def merge_defs(hunt: list[dict], card: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in with_scope(hunt, "hunt") + with_scope(card, "card"):
        fid = str(item.get("id") or "")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        out.append(item)
    return out


def concat_defs(groups: list[list], scope: str = "hunt") -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for group in groups:
        for item in with_scope(list(group or []), scope):
            fid = str(item.get("id") or "")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            out.append(item)
    return out


def is_check_on(value: str) -> bool:
    return value.strip().lower() in CHECK_TRUE


def field_bits(defs: list[dict], values: dict[str, str]) -> list[dict]:
    by_id = {str(item.get("id")): item for item in defs}
    bits: list[dict] = []
    for fid, raw in (values or {}).items():
        item = by_id.get(fid)
        if not item:
            continue
        value = str(raw or "").strip()
        kind = str(item.get("kind") or "text")
        if kind == "check":
            if not is_check_on(value):
                continue
            value = "да"
        if not value:
            continue
        bits.append(
            {
                "id": fid,
                "name": item.get("name") or fid,
                "kind": kind,
                "value": value,
                "scope": item.get("scope") or "hunt",
            }
        )
    return bits
