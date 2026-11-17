import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, select, tuple_

from app.models.message import Message


@dataclass(frozen=True, slots=True)
class MessageCursor:
    created_at: datetime
    message_id: uuid.UUID


def build_message_history_query(
    room_id: uuid.UUID,
    *,
    before: MessageCursor | None = None,
    page_size: int = 50,
) -> Select[tuple[Message]]:
    """Build a stable newest-first PostgreSQL history query.

    One extra row is fetched so a later API service can determine whether to
    return another cursor. Authentication and membership remain later concerns.
    """
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")

    statement = select(Message).where(Message.room_id == room_id)
    if before is not None:
        statement = statement.where(
            tuple_(Message.created_at, Message.id) < tuple_(before.created_at, before.message_id)
        )
    return statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(page_size + 1)
