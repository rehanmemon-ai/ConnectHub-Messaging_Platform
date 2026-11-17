import uuid

from fastapi import APIRouter, Request

from app.ai.provider import build_provider
from app.ai.schemas import (
    BackfillRequest,
    BackfillResult,
    EmbeddingStatus,
    SummaryRequest,
    SummaryView,
)
from app.ai.service import (
    embedding_status,
    queue_backfill,
    semantic_search,
    summarize_room,
)
from app.identity.dependencies import AppSettings, CurrentAuth, DatabaseSession
from app.messaging.schemas import SemanticSearchRequest, SemanticSearchResponse
from app.security.http import require_csrf

router = APIRouter(prefix="/api/v1/rooms/{room_id}", tags=["ai"])


@router.post("/summaries", response_model=SummaryView)
async def post_summary(
    room_id: uuid.UUID,
    data: SummaryRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> SummaryView:
    require_csrf(request, context.session, settings)
    return await summarize_room(
        db,
        context,
        room_id,
        max_messages=data.max_messages or settings.ai_max_summary_messages,
        provider=build_provider(settings),
        settings=settings,
    )


@router.post("/messages/semantic-search", response_model=SemanticSearchResponse)
async def post_semantic_search(
    room_id: uuid.UUID,
    data: SemanticSearchRequest,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> SemanticSearchResponse:
    return await semantic_search(
        db,
        context,
        room_id,
        query=data.query,
        limit=data.limit,
        provider=build_provider(settings),
        settings=settings,
    )


@router.get("/embeddings/status", response_model=EmbeddingStatus)
async def get_embedding_status(
    room_id: uuid.UUID,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> EmbeddingStatus:
    return await embedding_status(db, context, room_id, settings)


@router.post("/embeddings/backfill", response_model=BackfillResult)
async def post_embedding_backfill(
    room_id: uuid.UUID,
    data: BackfillRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> BackfillResult:
    require_csrf(request, context.session, settings)
    return BackfillResult(queued=await queue_backfill(db, context, room_id, data.limit, settings))
