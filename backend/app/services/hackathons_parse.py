"""Parse public hackathon calendars into normalized event dicts."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape

TILDA_FEED = "https://feeds.tildacdn.com/api/getfeed/"
HACKRUS_UPCOMING = ("617755803461", "488755787")
HACKRUS_PAST = ("617755803461", "860725534")
HACKRUS_RESULTS = ("303105619431", "488758159")
HACKPRO_ACTIVE = ("131632209651-986950497851", "442995264")
HACKPRO_ARCHIVE = ("131632209651-561890134691", "514826123")
ODS_PAGE = "https://ods.ai/competitions"

_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
_RANGE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:[-–—]\s*(?P<d2>\d{1,2})\s*)?(?P<m>[а-яА-ЯёЁ]+)\s+(?P<y>\d{4})",
    re.I,
)
_PRIZE = re.compile(
    r"(?:призовой\s+фонд\s*[:\-]?\s*)?(?:за\s+)?(?P<amount>\d[\d\s.,]*)\s*(?P<unit>млн|тыс\.?|тысяч)?\s*(?P<cur>₽|руб\.?|rub)",
    re.I,
)
_ORGANIZER = re.compile(
    r"(?:от|организатор[аы]?|организует)\s+[«\"“]?([^»\"”\n,.]{2,80})[»\"”]?",
    re.I,
)
_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.I | re.S)

SOURCE_LABELS = {
    "hackrus": "Хакатоны.рус",
    "hackathons_pro": "Hackathons.pro",
    "ods": "ODS.ai",
}

# Tilda feeds refuse requests unless Referer matches the project domain.
SOURCE_REFERERS = {
    "hackrus": "https://xn--80aa3anexr8c.xn--p1acf/",  # хакатоны.рус
    "hackathons_pro": "https://hackathons.pro/",
    "ods": "https://ods.ai/",
}


def _clean(text: str | None) -> str:
    raw = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", raw).strip()


def _parse_tilda_dt(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_range(blob: str) -> tuple[datetime | None, datetime | None]:
    match = _RANGE.search(blob or "")
    if not match:
        return None, None
    month = _MONTHS.get(match.group("m").casefold())
    if not month:
        return None, None
    year = int(match.group("y"))
    start = datetime(year, month, int(match.group("d1")))
    end_day = match.group("d2")
    end = datetime(year, month, int(end_day)) if end_day else None
    return start, end


def _parts(post: dict) -> list[str]:
    titles = [
        str(item.get("parttitle") or "").strip()
        for item in post.get("postparts") or []
        if isinstance(item, dict)
    ]
    if titles:
        return [item for item in titles if item]
    return [part.strip() for part in str(post.get("parts") or "").split(",") if part.strip()]


def _registration_from_parts(parts: list[str]) -> str:
    blob = " ".join(parts).casefold()
    if "регистрация открыта" in blob or "активные" in {p.casefold() for p in parts}:
        return "open"
    if any(token in blob for token in ("регистрация закрыта", "завершен", "завершён", "итоги", "прошедш")):
        return "closed"
    if "регистрация" in blob:
        return "open" if "открыт" in blob else "closed"
    return "unknown"


def _format_from_parts(parts: list[str]) -> str | None:
    lowered = {part.casefold() for part in parts}
    online = "online" in lowered or "онлайн" in lowered
    offline = "offline" in lowered or "офлайн" in lowered or "оффлайн" in lowered
    if online and offline:
        return "hybrid"
    if online:
        return "online"
    if offline:
        return "offline"
    return None


def _location_from_parts(parts: list[str]) -> str | None:
    skip = {
        "online",
        "offline",
        "онлайн",
        "офлайн",
        "оффлайн",
        "регистрация открыта",
        "регистрация закрыта",
        "активные",
        "архив",
        "ctf",
        "ml",
        "gamejam",
    }
    cities = [part for part in parts if part.casefold() not in skip and "регистрац" not in part.casefold()]
    return ", ".join(cities[:3]) or None


def _prize_from_text(*blobs: str) -> str | None:
    for blob in blobs:
        match = _PRIZE.search(blob or "")
        if not match:
            continue
        amount = re.sub(r"\s+", " ", match.group("amount")).strip(" .,")
        unit = (match.group("unit") or "").strip().casefold()
        cur = "₽"
        if unit.startswith("млн"):
            return f"{amount} млн {cur}"
        if unit.startswith("тыс") or unit.startswith("тысяч"):
            return f"{amount} тыс. {cur}"
        return f"{amount} {cur}"
    return None


def _organizer_from_text(*blobs: str) -> str | None:
    for blob in blobs:
        match = _ORGANIZER.search(blob or "")
        if not match:
            continue
        name = _clean(match.group(1))
        name = re.sub(r"\s+при\s+поддержке.*$", "", name, flags=re.I).strip(" .,—-")
        if len(name) >= 2 and "призов" not in name.casefold():
            return name[:255]
    return None


def _image_from_post(post: dict) -> str | None:
    for key in ("image", "mediadata", "thumb"):
        raw = str(post.get(key) or "").strip()
        if raw.startswith("http"):
            return raw[:1024]
    preview = post.get("preview-media")
    if isinstance(preview, dict):
        source = preview.get("source")
        if isinstance(source, dict):
            raw = str(source.get("url") or "").strip()
            if raw.startswith("http"):
                return raw[:1024]
    return None


def parse_tilda_feed(
    payload: dict | None,
    *,
    source: str,
    default_event_status: str,
) -> list[dict]:
    posts = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(posts, list):
        return []
    out: list[dict] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        source_id = str(post.get("uid") or "").strip()
        title = _clean(str(post.get("title") or ""))
        url = str(post.get("url") or "").strip()
        if not source_id or not title or not url:
            continue
        parts = _parts(post)
        descr = _clean(str(post.get("descr") or post.get("text") or ""))
        starts, ends = _parse_range(descr)
        feed_dt = _parse_tilda_dt(str(post.get("date") or ""))
        if starts is None and feed_dt is not None:
            starts = feed_dt
        if ends is None and feed_dt is not None and default_event_status == "finished":
            ends = feed_dt
        registration = _registration_from_parts(parts)
        if default_event_status == "finished":
            registration = "closed" if registration == "unknown" else registration
            event_status = "finished"
        else:
            event_status = default_event_status
        out.append(
            {
                "source": source,
                "source_id": source_id,
                "title": title[:512],
                "url": url[:1024],
                "description": descr[:4000] or None,
                "starts_at": starts,
                "ends_at": ends,
                "registration_status": registration,
                "event_status": event_status,
                "format": _format_from_parts(parts),
                "location": _location_from_parts(parts),
                "tags": ", ".join(parts)[:512] or None,
                "prize_text": _prize_from_text(descr, title),
                "organizer": _organizer_from_text(title, descr),
                "image_url": _image_from_post(post),
            }
        )
    return out


def _ods_dt(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_ods_competition(row: dict, *, bucket: str) -> dict | None:
    source_id = str(row.get("id") or row.get("slug") or "").strip()
    title = _clean(str(row.get("title") or ""))
    slug = str(row.get("slug") or "").strip()
    if not source_id or not title:
        return None
    dates = row.get("dates") if isinstance(row.get("dates"), dict) else {}
    status = row.get("status") if isinstance(row.get("status"), dict) else {}
    starts = _ods_dt(str(dates.get("start_date") or ""))
    ends = _ods_dt(str(dates.get("final_date") or ""))
    if status.get("is_finished") or bucket == "past":
        event_status = "finished"
    elif status.get("is_started"):
        event_status = "active"
    else:
        event_status = "upcoming"
    if status.get("is_registration_available"):
        registration = "open"
    elif event_status == "finished":
        registration = "closed"
    else:
        registration = "closed" if status.get("is_started") else "unknown"
    tags: list[str] = []
    type_row = row.get("type") if isinstance(row.get("type"), dict) else {}
    if type_row.get("name"):
        tags.append(str(type_row["name"]))
    for item in row.get("tags") or []:
        if isinstance(item, dict) and item.get("name"):
            tags.append(str(item["name"]))
        elif isinstance(item, str):
            tags.append(item)
    platform = row.get("platform") if isinstance(row.get("platform"), dict) else {}
    hubs = [item for item in row.get("related_hubs") or [] if isinstance(item, dict)]
    organizer = None
    if hubs:
        organizer = _clean(str(hubs[0].get("title") or "")) or None
    if not organizer:
        platform_name = str(platform.get("name") or "").strip()
        if platform_name and platform_name.casefold() not in {"ods", "ods.ai", "opendatascience"}:
            organizer = platform_name
    prize = None
    cash = row.get("reward_cash")
    if isinstance(cash, (int, float)) and cash > 0:
        prize = f"{int(cash):,} ₽".replace(",", " ")
    else:
        prize = _prize_from_text(_clean(str(row.get("description") or "")), title)
    image = None
    for key in ("image_rectangle", "image", "cover", "logo"):
        raw = str(row.get(key) or "").strip()
        if raw.startswith("http"):
            image = raw[:1024]
            break
    if not image and hubs:
        icon = str(hubs[0].get("icon") or "").strip()
        if icon.startswith("http"):
            image = icon[:1024]
    return {
        "source": "ods",
        "source_id": source_id,
        "title": title[:512],
        "url": f"https://ods.ai/competitions/{slug}" if slug else f"https://ods.ai/competitions/{source_id}",
        "description": _clean(str(row.get("description") or ""))[:4000] or None,
        "starts_at": starts,
        "ends_at": ends,
        "registration_status": registration,
        "event_status": event_status,
        "format": "online",
        "location": str(platform.get("name") or "ODS") or None,
        "tags": ", ".join(tags)[:512] or None,
        "prize_text": prize,
        "organizer": organizer[:255] if organizer else None,
        "image_url": image,
    }


def parse_ods_page(html: str) -> list[dict]:
    match = _NEXT.search(html or "")
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    page = data.get("props", {}).get("pageProps", {})
    out: list[dict] = []
    for bucket, key in (("active", "activePageData"), ("past", "pastPageData")):
        block = page.get(key) if isinstance(page, dict) else None
        rows = block.get("competitions") if isinstance(block, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = parse_ods_competition(row, bucket=bucket)
            if item:
                out.append(item)
    return out


def parse_ods_fixture(payload: dict) -> list[dict]:
    out: list[dict] = []
    for bucket in ("active", "past"):
        for row in payload.get(bucket) or []:
            if isinstance(row, dict):
                item = parse_ods_competition(row, bucket=bucket)
                if item:
                    out.append(item)
    return out
