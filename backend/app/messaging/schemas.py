import unicodedata
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.identity.schemas import PublicUser


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SendMessageRequest(StrictModel):
    client_id: uuid.UUID
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        if not 1 <= len(normalized) <= 4000:
            raise ValueError("Message content must be 1-4000 characters.")
        return normalized


class MessageView(StrictModel):
    id: uuid.UUID
    room_id: uuid.UUID
    sender: PublicUser
    content: str
    created_at: datetime


class MessageEnvelope(StrictModel):
    message: MessageView
    idempotent_replay: bool = False


class MessagePage(StrictModel):
    items: list[MessageView]
    next_cursor: str | None


class ReadPositionRequest(StrictModel):
    message_id: uuid.UUID


class ReadReceiptView(StrictModel):
    room_id: uuid.UUID
    user: PublicUser
    message_id: uuid.UUID
    read_at: datetime


class ReadReceiptEnvelope(StrictModel):
    receipt: ReadReceiptView


class MessageSearchPage(StrictModel):
    items: list[MessageView]
    next_cursor: str | None


class SemanticSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = unicodedata.normalize("NFKC", value).strip()
        if not value:
            raise ValueError("Search query cannot be empty.")
        return value


class SemanticMessageResult(StrictModel):
    message: MessageView
    similarity: float


class SemanticSearchResponse(StrictModel):
    items: list[SemanticMessageResult]
    total_messages: int
    indexed_messages: int
    indexed_candidates: int
    unindexed_messages: int
    candidate_limit: int
    candidate_window_truncated: bool
    failed_jobs: int
    embedding_profile: str
