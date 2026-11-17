import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NotificationView(StrictModel):
    id: uuid.UUID
    type: str
    room_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    message_id: uuid.UUID | None
    invitation_id: uuid.UUID | None
    metadata: dict[str, object]
    created_at: datetime
    read_at: datetime | None


class NotificationEnvelope(StrictModel):
    notification: NotificationView


class NotificationPage(StrictModel):
    items: list[NotificationView]
    next_cursor: str | None


class UnreadCount(StrictModel):
    count: int
