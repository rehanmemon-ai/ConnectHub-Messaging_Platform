import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.identity.service import AuthContext
from app.models import Notification
from app.notifications.schemas import NotificationPage, NotificationView
from app.rooms.cursors import Cursor, encode_cursor


def notification_view(item: Notification) -> NotificationView:
    return NotificationView(
        id=item.id,
        type=item.type,
        room_id=item.room_id,
        actor_id=item.actor_id,
        message_id=item.message_id,
        invitation_id=item.invitation_id,
        metadata=item.metadata_json,
        created_at=item.created_at,
        read_at=item.read_at,
    )


async def list_notifications(
    db: AsyncSession,
    context: AuthContext,
    *,
    cursor: Cursor | None,
    limit: int,
) -> NotificationPage:
    statement = (
        select(Notification)
        .where(Notification.user_id == context.user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        statement = statement.where(
            tuple_(Notification.created_at, Notification.id)
            < tuple_(cursor.timestamp, cursor.item_id)
        )
    rows = (await db.scalars(statement)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id)
    return NotificationPage(
        items=[notification_view(item) for item in page], next_cursor=next_cursor
    )


async def unread_count(db: AsyncSession, context: AuthContext) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == context.user.id, Notification.read_at.is_(None))
        )
        or 0
    )


async def mark_notification_read(
    db: AsyncSession, context: AuthContext, notification_id: uuid.UUID
) -> NotificationView:
    item = await db.scalar(
        select(Notification)
        .where(Notification.id == notification_id, Notification.user_id == context.user.id)
        .with_for_update()
    )
    if item is None:
        raise ApiError(404, "notification_not_found", "The notification does not exist.")
    if item.read_at is None:
        item.read_at = datetime.now(UTC)
        await db.commit()
    return notification_view(item)


async def mark_all_notifications_read(db: AsyncSession, context: AuthContext) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == context.user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    return int(result.rowcount or 0)
