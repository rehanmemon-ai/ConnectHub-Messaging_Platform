import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SummaryRequest(StrictModel):
    max_messages: int | None = Field(default=None, ge=1, le=500)


class SummaryView(StrictModel):
    id: uuid.UUID
    room_id: uuid.UUID
    provider: str
    model: str
    prompt_version: str
    content: str
    source_start_id: uuid.UUID
    source_end_id: uuid.UUID
    source_message_count: int
    source_truncated: bool
    input_characters: int
    created_at: datetime
    cached: bool


class EmbeddingStatus(StrictModel):
    total_messages: int
    indexed_messages: int
    pending_jobs: int
    failed_jobs: int
    provider: str
    model: str
    embedding_profile: str
    candidate_limit: int
    storage: str = "postgresql_jsonb_exact_cosine"


class BackfillRequest(StrictModel):
    limit: int = Field(default=100, ge=1, le=500)


class BackfillResult(StrictModel):
    queued: int
