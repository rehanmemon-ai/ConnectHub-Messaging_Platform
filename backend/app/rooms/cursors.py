import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.api.errors import ApiError


@dataclass(frozen=True, slots=True)
class Cursor:
    timestamp: datetime
    item_id: uuid.UUID


def encode_cursor(timestamp: datetime, item_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"timestamp": timestamp.isoformat(), "id": str(item_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> Cursor | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(value + padding)
        payload = json.loads(raw)
        if set(payload) != {"timestamp", "id"}:
            raise ValueError
        timestamp = datetime.fromisoformat(payload["timestamp"])
        if timestamp.tzinfo is None:
            raise ValueError
        item_id = uuid.UUID(payload["id"])
    except (TypeError, ValueError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        raise ApiError(400, "invalid_cursor", "The pagination cursor is invalid.") from None
    return Cursor(timestamp=timestamp, item_id=item_id)
