import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.messaging.schemas import SendMessageRequest


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubscribeEvent(Event):
    type: Literal["room.subscribe"]
    room_id: uuid.UUID


class UnsubscribeEvent(Event):
    type: Literal["room.unsubscribe"]
    room_id: uuid.UUID


class MessageSendEvent(SendMessageRequest):
    type: Literal["message.send"]
    room_id: uuid.UUID


class TypingStartedEvent(Event):
    type: Literal["typing.start"]
    room_id: uuid.UUID


class TypingStoppedEvent(Event):
    type: Literal["typing.stop"]
    room_id: uuid.UUID


class ReadPositionEvent(Event):
    type: Literal["read.update"]
    room_id: uuid.UUID
    message_id: uuid.UUID


class PingEvent(Event):
    type: Literal["ping"]
    nonce: str = Field(default="", max_length=100)


ClientEvent = Annotated[
    SubscribeEvent
    | UnsubscribeEvent
    | MessageSendEvent
    | TypingStartedEvent
    | TypingStoppedEvent
    | ReadPositionEvent
    | PingEvent,
    Field(discriminator="type"),
]

client_event_adapter = TypeAdapter(ClientEvent)
