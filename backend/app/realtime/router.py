import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.websockets import WebSocketDisconnected

from app.api.errors import ApiError
from app.core.config import get_settings
from app.db.session import get_engine
from app.identity.service import find_live_session
from app.messaging.schemas import SendMessageRequest
from app.messaging.service import require_room_membership, send_message, update_read_position
from app.models import User
from app.realtime.manager import Connection, connection_manager
from app.realtime.schemas import (
    MessageSendEvent,
    PingEvent,
    ReadPositionEvent,
    SubscribeEvent,
    TypingStartedEvent,
    TypingStoppedEvent,
    UnsubscribeEvent,
    client_event_adapter,
)
from app.security.rate_limit import rate_limiter

router = APIRouter(tags=["realtime"])


async def _send_error(
    connection: Connection,
    code: str,
    message: str,
    *,
    recoverable: bool = True,
    wait_for_delivery: bool = False,
) -> None:
    sender = (
        connection_manager.enqueue_and_wait if wait_for_delivery else connection_manager.enqueue
    )
    await sender(
        connection,
        {
            "type": "error",
            "error": {"code": code, "message": message, "recoverable": recoverable},
        },
    )


async def _handle_event(connection: Connection, event, context, db, settings) -> None:  # type: ignore[no-untyped-def]
    if isinstance(event, PingEvent):
        await connection_manager.enqueue(
            connection,
            {"type": "pong", "nonce": event.nonce, "timestamp": datetime.now(UTC).isoformat()},
        )
        return
    if isinstance(event, SubscribeEvent):
        await require_room_membership(db, event.room_id, context.user.id)
        await connection_manager.subscribe(connection, event.room_id)
        await connection_manager.enqueue(
            connection, {"type": "room.subscribed", "room_id": str(event.room_id)}
        )
        count = await connection_manager.room_user_connection_count(event.room_id, context.user.id)
        await connection_manager.broadcast_room(
            event.room_id,
            {
                "type": "presence.changed",
                "room_id": str(event.room_id),
                "user_id": str(context.user.id),
                "status": "online",
                "connection_count": count,
            },
        )
        return
    if isinstance(event, UnsubscribeEvent):
        await connection_manager.unsubscribe(connection, event.room_id)
        await connection_manager.enqueue(
            connection, {"type": "room.unsubscribed", "room_id": str(event.room_id)}
        )
        count = await connection_manager.room_user_connection_count(event.room_id, context.user.id)
        if count == 0:
            await connection_manager.broadcast_room(
                event.room_id,
                {
                    "type": "presence.changed",
                    "room_id": str(event.room_id),
                    "user_id": str(context.user.id),
                    "status": "offline",
                    "connection_count": 0,
                },
            )
        return

    room_id = event.room_id
    if room_id not in connection.subscriptions:
        raise ApiError(403, "room_subscription_required", "Subscribe to the room first.")
    if isinstance(event, MessageSendEvent):
        await rate_limiter.check(
            f"ws-message:{context.user.id}",
            limit=settings.message_rate_limit,
            window_seconds=settings.rate_limit_window_seconds,
        )
        sent = await send_message(
            db,
            context,
            room_id,
            SendMessageRequest(client_id=event.client_id, content=event.content),
            settings,
        )
        if sent.created:
            await connection_manager.broadcast_room(
                room_id,
                {"type": "message.created", "message": sent.message.model_dump(mode="json")},
            )
            for user_id in sent.notification_user_ids:
                await connection_manager.broadcast_user(
                    user_id,
                    {
                        "type": "notification.created",
                        "notification_type": "message_mention",
                    },
                )
        else:
            await connection_manager.enqueue(
                connection,
                {
                    "type": "message.replayed",
                    "message": sent.message.model_dump(mode="json"),
                },
            )
        return
    if isinstance(event, ReadPositionEvent):
        receipt = await update_read_position(db, context, room_id, event.message_id)
        await connection_manager.broadcast_room(
            room_id,
            {"type": "read_receipt.changed", "receipt": receipt.model_dump(mode="json")},
        )
        return
    if isinstance(event, TypingStartedEvent):
        await require_room_membership(db, room_id, context.user.id)
        await rate_limiter.check(
            f"typing:{connection.id}:{room_id}",
            limit=1,
            window_seconds=max(1, int(settings.typing_throttle_seconds)),
        )
        await connection_manager.start_typing(
            connection,
            room_id,
            {
                "type": "typing.started",
                "room_id": str(room_id),
                "user": {
                    "id": str(context.user.id),
                    "username": context.user.username,
                    "display_name": context.user.display_name,
                },
            },
            settings.typing_expiry_seconds,
        )
        return
    if isinstance(event, TypingStoppedEvent):
        await connection_manager.stop_typing(connection, room_id)


async def _websocket_session(websocket: WebSocket, initial_room_id: uuid.UUID | None) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")
    if origin not in settings.allowed_origins:
        await websocket.close(code=4403, reason="origin_denied")
        return
    raw_token = websocket.cookies.get(settings.session_cookie_name)
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as db:
        context = await find_live_session(db, raw_token)
        if context is None:
            await websocket.close(code=4401, reason="authentication_required")
            return
        if initial_room_id is not None:
            try:
                await require_room_membership(db, initial_room_id, context.user.id)
            except ApiError:
                await websocket.close(code=4404, reason="room_unavailable")
                return

    await websocket.accept()
    try:
        connection = await connection_manager.register(
            websocket,
            user_id=context.user.id,
            session_id=context.session.id,
            queue_size=settings.websocket_queue_size,
            connection_limit=settings.websocket_connection_limit,
        )
    except RuntimeError:
        await websocket.close(code=4429, reason="connection_limit")
        return
    if initial_room_id is not None:
        await connection_manager.subscribe(connection, initial_room_id)
    await connection_manager.enqueue(
        connection,
        {
            "type": "connection.ready",
            "protocol": "connecthub.v1",
            "connection_id": str(connection.id),
            "user_id": str(context.user.id),
            "subscriptions": [str(value) for value in connection.subscriptions],
        },
    )
    for room_id in connection.subscriptions:
        count = await connection_manager.room_user_connection_count(room_id, context.user.id)
        await connection_manager.broadcast_room(
            room_id,
            {
                "type": "presence.changed",
                "room_id": str(room_id),
                "user_id": str(context.user.id),
                "status": "online",
                "connection_count": count,
            },
        )

    malformed = 0
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=settings.websocket_idle_timeout_seconds
                )
            except TimeoutError:
                await websocket.close(code=4008, reason="heartbeat_timeout")
                break
            if len(raw.encode("utf-8")) > settings.websocket_frame_bytes:
                await _send_error(
                    connection,
                    "frame_too_large",
                    "The event exceeds 16 KiB.",
                    recoverable=False,
                    wait_for_delivery=True,
                )
                await websocket.close(code=1009, reason="frame_too_large")
                break
            try:
                payload = json.loads(raw)
                event = client_event_adapter.validate_python(payload)
            except (json.JSONDecodeError, ValidationError):
                malformed += 1
                await _send_error(
                    connection,
                    "invalid_event",
                    "The event is invalid.",
                    wait_for_delivery=malformed >= settings.websocket_malformed_limit,
                )
                if malformed >= settings.websocket_malformed_limit:
                    await websocket.close(code=1008, reason="too_many_invalid_events")
                    break
                continue
            async with factory() as db:
                live = await find_live_session(db, raw_token)
                if live is None or live.session.id != context.session.id:
                    await _send_error(
                        connection,
                        "session_expired",
                        "The session is no longer valid.",
                        recoverable=False,
                        wait_for_delivery=True,
                    )
                    await websocket.close(code=4401, reason="session_expired")
                    break
                try:
                    await _handle_event(connection, event, live, db, settings)
                except ApiError as error:
                    await db.rollback()
                    await _send_error(connection, error.code, error.message)
    except (WebSocketDisconnect, WebSocketDisconnected):
        pass
    finally:
        subscribed_rooms = tuple(connection.subscriptions)
        still_online = await connection_manager.disconnect(connection)
        for room_id in subscribed_rooms:
            count = await connection_manager.room_user_connection_count(room_id, context.user.id)
            if count == 0:
                await connection_manager.broadcast_room(
                    room_id,
                    {
                        "type": "presence.changed",
                        "room_id": str(room_id),
                        "user_id": str(context.user.id),
                        "status": "offline",
                        "connection_count": 0,
                    },
                )
        if not still_online:
            async with factory() as db:
                user = await db.get(User, context.user.id)
                if user is not None:
                    user.last_seen_at = datetime.now(UTC)
                    await db.commit()


@router.websocket("/ws")
async def websocket_root(websocket: WebSocket) -> None:
    await _websocket_session(websocket, None)


@router.websocket("/ws/rooms/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: uuid.UUID) -> None:
    await _websocket_session(websocket, room_id)
