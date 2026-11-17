import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.identity.dependencies import AppSettings, CurrentAuth, DatabaseSession
from app.messaging.schemas import (
    MessageEnvelope,
    MessagePage,
    ReadPositionRequest,
    ReadReceiptEnvelope,
    ReadReceiptView,
    SendMessageRequest,
)
from app.messaging.service import (
    list_messages,
    list_read_receipts,
    send_message,
    update_read_position,
)
from app.realtime.manager import connection_manager
from app.rooms.cursors import decode_cursor
from app.security.http import require_csrf
from app.security.rate_limit import rate_limiter

router = APIRouter(prefix="/api/v1/rooms/{room_id}", tags=["messages"])


@router.post("/messages", status_code=201, response_model=MessageEnvelope)
async def post_message(
    room_id: uuid.UUID,
    data: SendMessageRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> MessageEnvelope:
    require_csrf(request, context.session, settings)
    await rate_limiter.check(
        f"message:{context.user.id}",
        limit=settings.message_rate_limit,
        window_seconds=settings.rate_limit_window_seconds,
    )
    sent = await send_message(db, context, room_id, data, settings)
    if sent.created:
        await connection_manager.broadcast_room(
            room_id, {"type": "message.created", "message": sent.message.model_dump(mode="json")}
        )
        for user_id in sent.notification_user_ids:
            await connection_manager.broadcast_user(
                user_id, {"type": "notification.created", "notification_type": "message_mention"}
            )
    return MessageEnvelope(message=sent.message, idempotent_replay=not sent.created)


@router.get("/messages", response_model=MessagePage)
async def get_messages(
    room_id: uuid.UUID,
    context: CurrentAuth,
    db: DatabaseSession,
    before: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    return await list_messages(db, context, room_id, cursor=decode_cursor(before), limit=limit)


@router.get("/messages/search", response_model=MessagePage)
async def search_messages(
    room_id: uuid.UUID,
    context: CurrentAuth,
    db: DatabaseSession,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    query = q.strip()
    if not query:
        from app.api.errors import ApiError

        raise ApiError(422, "validation_error", "Search query cannot be empty.")
    return await list_messages(
        db, context, room_id, cursor=decode_cursor(cursor), limit=limit, search=query
    )


@router.put("/read-position", response_model=ReadReceiptEnvelope)
async def put_read_position(
    room_id: uuid.UUID,
    data: ReadPositionRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> ReadReceiptEnvelope:
    require_csrf(request, context.session, settings)
    receipt = await update_read_position(db, context, room_id, data.message_id)
    await connection_manager.broadcast_room(
        room_id, {"type": "read_receipt.changed", "receipt": receipt.model_dump(mode="json")}
    )
    return ReadReceiptEnvelope(receipt=receipt)


@router.get("/read-receipts", response_model=list[ReadReceiptView])
async def get_read_receipts(
    room_id: uuid.UUID, context: CurrentAuth, db: DatabaseSession
) -> list[ReadReceiptView]:
    return await list_read_receipts(db, context, room_id)
