"""One extra per aggregator / career board — not one row per listing id."""

from __future__ import annotations


def source_identity(source: object, source_id: object = None) -> str:
    src = str(source or "").strip()
    if src == "career":
        slug = str(source_id or "").split(":", 1)[0].strip()
        return f"career:{slug}" if slug else "career"
    return src


def compact_extra_sources(
    extras: object,
    *,
    source: object = None,
    source_id: object = None,
) -> list[dict]:
    if not isinstance(extras, list):
        return []
    seen: set[str] = set()
    labels: set[str] = set()
    primary = source_identity(source, source_id)
    if primary:
        seen.add(primary)
    out: list[dict] = []
    for raw in extras:
        if not isinstance(raw, dict):
            continue
        key = source_identity(raw.get("source"), raw.get("source_id"))
        if not key or key in seen:
            continue
        label = str(raw.get("label") or "").strip().lower()
        if label and label in labels:
            continue
        seen.add(key)
        if label:
            labels.add(label)
        out.append(raw)
    return out
