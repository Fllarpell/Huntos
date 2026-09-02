import re
from dataclasses import dataclass

_TG_HOST = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/+",
    re.IGNORECASE,
)
_USERNAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{3,31}$")


def normalize_telegram_alias(raw: str | None) -> str | None:
    """Strip @ / t.me prefixes. Empty input clears the field."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    text = _TG_HOST.sub("", text)
    text = text.lstrip("@").split("?")[0].split("#")[0].strip().strip("/")
    if not text:
        return None
    return text[:128]


def telegram_chat_url(alias: str | None) -> str | None:
    handle = normalize_telegram_alias(alias)
    if not handle:
        return None
    if handle.startswith("+"):
        return f"https://t.me/{handle}"
    return f"https://t.me/{handle}"


@dataclass(frozen=True)
class ChannelRef:
    username: str
    invite_hash: str | None
    added_url: str


def parse_channel_url(raw: str) -> ChannelRef:
    """Accept @name, t.me/name, t.me/s/name, t.me/name/123, t.me/+hash."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("Вставь ссылку на канал или @username")
    added_url = text
    text = _TG_HOST.sub("", text)
    text = text.split("?")[0].split("#")[0].strip().strip("/")
    if text.lower().startswith("s/"):
        text = text[2:]
    if text.lower().startswith("joinchat/"):
        token = text.split("/", 1)[1].strip()
        if not token:
            raise ValueError("Приватный инвайт без ключа")
        return ChannelRef(username=f"+{token}"[:128], invite_hash=token, added_url=added_url)
    if text.startswith("+"):
        token = text[1:].split("/")[0].strip()
        if not token:
            raise ValueError("Приватный инвайт без ключа")
        return ChannelRef(username=f"+{token}"[:128], invite_hash=token, added_url=added_url)
    head = text.lstrip("@").split("/")[0]
    if not _USERNAME.match(head):
        raise ValueError("Нужен публичный @username канала или инвайт t.me/+…")
    return ChannelRef(username=head.lower(), invite_hash=None, added_url=added_url)

