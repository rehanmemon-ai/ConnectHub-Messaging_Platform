import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.identity.dependencies import AppSettings, CurrentAuth, DatabaseSession
from app.notifications.schemas import (
    NotificationEnvelope,
    NotificationPage,
    UnreadCount,
)
from app.notifications.service import (
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    unread_count,
)
from app.rooms.cursors import decode_cursor
from app.security.http import require_csrf

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def get_notifications(
    context: CurrentAuth,
    db: DatabaseSession,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationPage:
    return await list_notifications(db, context, cursor=decode_cursor(cursor), limit=limit)


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(context: CurrentAuth, db: DatabaseSession) -> UnreadCount:
    return UnreadCount(count=await unread_count(db, context))


@router.post("/read-all", response_model=UnreadCount)
async def post_read_all(
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> UnreadCount:
    require_csrf(request, context.session, settings)
    return UnreadCount(count=await mark_all_notifications_read(db, context))


@router.post("/{notification_id}/read", response_model=NotificationEnvelope)
async def post_notification_read(
    notification_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> NotificationEnvelope:
    require_csrf(request, context.session, settings)
    return NotificationEnvelope(
        notification=await mark_notification_read(db, context, notification_id)
    )
