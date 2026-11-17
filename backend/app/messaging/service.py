import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import embedding_profile
from app.api.errors import ApiError
from app.core.config import Settings
from app.identity.schemas import PublicUser
from app.identity.service import AuthContext
from app.messaging.schemas import (
    MessagePage,
    MessageView,
    ReadReceiptView,
    SendMessageRequest,
)
from app.models import EmbeddingJob, Message, Notification, Room, RoomMembership, User
from app.rooms.cursors import Cursor, encode_cursor
from app.rooms.service import lock_membership_for_update

MENTION_PATTERN = re.compile(r"(?<![\w@])@([\w.-]{1,50})", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SentMessage:
    message: MessageView
    created: bool
    notification_user_ids: tuple[uuid.UUID, ...]


def message_view(message: Message, sender: User) -> MessageView:
    return MessageView(
        id=message.id,
        room_id=message.room_id,
        sender=PublicUser.model_validate(sender),
        content=message.content,
        created_at=message.created_at,
    )


async def require_room_membership(
    db: AsyncSession, room_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
) -> RoomMembership:
    membership = (
        await lock_membership_for_update(db, room_id, user_id)
        if lock
        else await db.scalar(
            select(RoomMembership).where(
                RoomMembership.room_id == room_id,
                RoomMembership.user_id == user_id,
            )
        )
    )
    if membership is None:
        room = await db.scalar(select(Room).where(Room.id == room_id))
        if room is None or room.visibility == "private":
            raise ApiError(404, "room_not_found", "The room does not exist.")
        raise ApiError(403, "room_membership_required", "You are not a room member.")
    return membership


async def _load_message_view(db: AsyncSession, message_id: uuid.UUID) -> MessageView:
    row = (
        await db.execute(
            select(Message, User)
            .join(User, User.id == Message.sender_id)
            .where(Message.id == message_id)
        )
    ).one()
    return message_view(row[0], row[1])


async def send_message(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    data: SendMessageRequest,
    settings: Settings,
) -> SentMessage:
    await require_room_membership(db, room_id, context.user.id, lock=True)
    existing = (
        await db.execute(
            select(Message, User)
            .join(User, User.id == Message.sender_id)
            .where(
                Message.room_id == room_id,
                Message.sender_id == context.user.id,
                Message.client_idempotency_key == data.client_id,
            )
        )
    ).one_or_none()
    if existing is not None:
        if existing[0].content != data.content:
            raise ApiError(
                409,
                "idempotency_conflict",
                "The idempotency identifier was already used for different content.",
            )
        replay_view = message_view(existing[0], existing[1])
        await db.rollback()
        return SentMessage(replay_view, False, ())

    message = Message(
        room_id=room_id,
        sender_id=context.user.id,
        content=data.content,
        client_idempotency_key=data.client_id,
    )
    db.add(message)
    try:
        await db.flush()
        if settings.ai_enabled and settings.ai_auto_embed_new_messages:
            db.add(
                EmbeddingJob(
                    message_id=message.id,
                    status="pending",
                    profile=embedding_profile(settings),
                    origin="automatic",
                )
            )
        mentioned = {name.casefold() for name in MENTION_PATTERN.findall(data.content)}
        notified_ids: list[uuid.UUID] = []
        if mentioned:
            users = (
                await db.execute(
                    select(User)
                    .join(RoomMembership, RoomMembership.user_id == User.id)
                    .where(
                        RoomMembership.room_id == room_id,
                        func.lower(User.username).in_(mentioned),
                        User.id != context.user.id,
                    )
                )
            ).scalars()
            for user in users:
                db.add(
                    Notification(
                        user_id=user.id,
                        type="message_mention",
                        room_id=room_id,
                        actor_id=context.user.id,
                        message_id=message.id,
                        dedup_key=f"mention:{message.id}:{user.id}",
                        metadata_json={"message_id": str(message.id)},
                    )
                )
                notified_ids.append(user.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        replay = (
            await db.execute(
                select(Message, User)
                .join(User, User.id == Message.sender_id)
                .where(
                    Message.room_id == room_id,
                    Message.sender_id == context.user.id,
                    Message.client_idempotency_key == data.client_id,
                )
            )
        ).one_or_none()
        if replay is None:
            raise
        if replay[0].content != data.content:
            raise ApiError(
                409, "idempotency_conflict", "The idempotency identifier conflicts."
            ) from None
        return SentMessage(message_view(replay[0], replay[1]), False, ())

    return SentMessage(await _load_message_view(db, message.id), True, tuple(notified_ids))


async def list_messages(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    *,
    cursor: Cursor | None,
    limit: int,
    search: str | None = None,
) -> MessagePage:
    await require_room_membership(db, room_id, context.user.id)
    statement = (
        select(Message, User)
        .join(User, User.id == Message.sender_id)
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        statement = statement.where(
            tuple_(Message.created_at, Message.id) < tuple_(cursor.timestamp, cursor.item_id)
        )
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Message.content.ilike(f"%{escaped}%", escape="\\"))
    rows = (await db.execute(statement)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        next_cursor = encode_cursor(page[-1][0].created_at, page[-1][0].id)
    return MessagePage(
        items=[message_view(row[0], row[1]) for row in page], next_cursor=next_cursor
    )


async def update_read_position(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    message_id: uuid.UUID,
) -> ReadReceiptView:
    membership = await require_room_membership(db, room_id, context.user.id, lock=True)
    target = await db.scalar(
        select(Message).where(Message.id == message_id, Message.room_id == room_id)
    )
    if target is None:
        raise ApiError(400, "invalid_read_position", "The message is not in this room.")
    if membership.last_read_message_id is not None:
        current = await db.scalar(
            select(Message).where(Message.id == membership.last_read_message_id)
        )
        if current is not None and (target.created_at, target.id) < (
            current.created_at,
            current.id,
        ):
            raise ApiError(409, "read_position_regression", "Read progress cannot move backwards.")
    now = datetime.now(UTC)
    membership.last_read_message_id = target.id
    membership.last_read_at = now
    await db.commit()
    return ReadReceiptView(
        room_id=room_id,
        user=PublicUser.model_validate(context.user),
        message_id=target.id,
        read_at=now,
    )


async def list_read_receipts(
    db: AsyncSession, context: AuthContext, room_id: uuid.UUID
) -> list[ReadReceiptView]:
    await require_room_membership(db, room_id, context.user.id)
    rows = (
        await db.execute(
            select(RoomMembership, User)
            .join(User, User.id == RoomMembership.user_id)
            .where(
                RoomMembership.room_id == room_id,
                RoomMembership.last_read_message_id.is_not(None),
                RoomMembership.last_read_at.is_not(None),
            )
        )
    ).all()
    return [
        ReadReceiptView(
            room_id=room_id,
            user=PublicUser.model_validate(user),
            message_id=membership.last_read_message_id,
            read_at=membership.last_read_at,
        )
        for membership, user in rows
    ]
