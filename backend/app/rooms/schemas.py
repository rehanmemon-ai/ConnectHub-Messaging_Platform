import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRoomRequest(StrictModel):
    name: str
    description: str = ""
    visibility: Literal["public", "private"] = "public"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        if not 1 <= len(normalized) <= 100:
            raise ValueError("Room name must be 1-100 characters.")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        if len(normalized) > 500:
            raise ValueError("Room description cannot exceed 500 characters.")
        return normalized


class MembershipView(StrictModel):
    role: str
    joined_at: datetime


class RoomView(StrictModel):
    id: uuid.UUID
    name: str
    description: str
    visibility: Literal["public", "private"]
    membership: MembershipView | None
    created_at: datetime


class RoomEnvelope(StrictModel):
    room: RoomView


class RoomPage(StrictModel):
    items: list[RoomView]
    next_cursor: str | None


class MembershipRecord(StrictModel):
    room_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime


class MembershipEnvelope(StrictModel):
    membership: MembershipRecord


class JoinedRoom(StrictModel):
    room: RoomView
    role: str
    joined_at: datetime


class JoinedRoomPage(StrictModel):
    items: list[JoinedRoom]
    next_cursor: str | None


class InviteUserRequest(StrictModel):
    username: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = unicodedata.normalize("NFKC", value).strip().casefold()
        if not 1 <= len(value) <= 50:
            raise ValueError("Username must be 1-50 characters.")
        return value


class InvitationView(StrictModel):
    id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    inviter_username: str
    invitee_username: str
    status: str
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None


class InvitationEnvelope(StrictModel):
    invitation: InvitationView


class InvitationPage(StrictModel):
    items: list[InvitationView]
    next_cursor: str | None


class MemberView(StrictModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    role: str
    joined_at: datetime
    online: bool
    last_seen_at: datetime | None


class MemberPage(StrictModel):
    items: list[MemberView]
    next_cursor: str | None
