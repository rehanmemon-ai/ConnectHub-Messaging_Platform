import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.errors import ApiError
from app.identity.service import AuthContext
from app.models import Notification, Room, RoomInvitation, RoomMembership, User
from app.rooms.cursors import Cursor, encode_cursor
from app.rooms.schemas import (
    CreateRoomRequest,
    InvitationPage,
    InvitationView,
    InviteUserRequest,
    JoinedRoom,
    JoinedRoomPage,
    MemberPage,
    MembershipRecord,
    MembershipView,
    MemberView,
    RoomPage,
    RoomView,
)


def _room_view(room: Room, role: str | None, joined_at) -> RoomView:  # type: ignore[no-untyped-def]
    membership = None
    if role is not None and joined_at is not None:
        membership = MembershipView(role=role, joined_at=joined_at)
    return RoomView(
        id=room.id,
        name=room.name,
        description=room.description,
        visibility=room.visibility,
        membership=membership,
        created_at=room.created_at,
    )


async def create_room(db: AsyncSession, context: AuthContext, data: CreateRoomRequest) -> RoomView:
    room = Room(name=data.name, description=data.description, visibility=data.visibility)
    db.add(room)
    try:
        await db.flush()
        membership = RoomMembership(user_id=context.user.id, room_id=room.id, role="owner")
        db.add(membership)
        await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(room)
    await db.refresh(membership)
    return _room_view(room, membership.role, membership.joined_at)


async def list_public_rooms(
    db: AsyncSession,
    context: AuthContext,
    *,
    search: str | None,
    cursor: Cursor | None,
    limit: int,
) -> RoomPage:
    membership = RoomMembership
    statement = (
        select(Room, membership.role, membership.joined_at)
        .outerjoin(
            membership,
            and_(membership.room_id == Room.id, membership.user_id == context.user.id),
        )
        .order_by(Room.created_at.desc(), Room.id.desc())
        .limit(limit + 1)
        .where(Room.visibility == "public")
    )
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Room.name.ilike(f"%{escaped}%", escape="\\"))
    if cursor is not None:
        statement = statement.where(
            tuple_(Room.created_at, Room.id) < tuple_(cursor.timestamp, cursor.item_id)
        )
    rows = (await db.execute(statement)).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_room_view(row[0], row[1], row[2]) for row in page_rows]
    next_cursor = None
    if has_more and page_rows:
        room = page_rows[-1][0]
        next_cursor = encode_cursor(room.created_at, room.id)
    return RoomPage(items=items, next_cursor=next_cursor)


async def get_room(db: AsyncSession, context: AuthContext, room_id: uuid.UUID) -> RoomView:
    row = (
        await db.execute(
            select(Room, RoomMembership.role, RoomMembership.joined_at)
            .outerjoin(
                RoomMembership,
                and_(
                    RoomMembership.room_id == Room.id,
                    RoomMembership.user_id == context.user.id,
                ),
            )
            .where(Room.id == room_id)
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "room_not_found", "The room does not exist.")
    if row[0].visibility == "private" and row[1] is None:
        raise ApiError(404, "room_not_found", "The room does not exist.")
    return _room_view(row[0], row[1], row[2])


async def join_room(db: AsyncSession, context: AuthContext, room_id: uuid.UUID) -> MembershipRecord:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None or room.visibility == "private":
        raise ApiError(404, "room_not_found", "The room does not exist.")
    membership = RoomMembership(user_id=context.user.id, room_id=room_id, role="member")
    db.add(membership)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ApiError(409, "already_a_member", "You are already a member of this room.") from None
    await db.refresh(membership)
    return MembershipRecord(
        room_id=membership.room_id,
        user_id=membership.user_id,
        role=membership.role,
        joined_at=membership.joined_at,
    )


async def lock_membership_for_update(
    db: AsyncSession, room_id: uuid.UUID, user_id: uuid.UUID
) -> RoomMembership | None:
    """Lock one membership until transaction end.

    Task 4 message sends must call this helper before accepting a message.
    Membership removal calls the same helper before deletion, so PostgreSQL
    deterministically orders send versus removal on the target membership row.
    """
    return await db.scalar(
        select(RoomMembership)
        .where(RoomMembership.room_id == room_id, RoomMembership.user_id == user_id)
        .with_for_update()
    )


async def leave_room(db: AsyncSession, context: AuthContext, room_id: uuid.UUID) -> None:
    if await db.scalar(select(Room.id).where(Room.id == room_id)) is None:
        raise ApiError(404, "room_not_found", "The room does not exist.")
    membership = await lock_membership_for_update(db, room_id, context.user.id)
    if membership is None:
        raise ApiError(403, "room_membership_required", "You are not a room member.")
    if membership.role == "owner":
        raise ApiError(409, "owner_cannot_leave", "The room owner cannot leave the room.")
    await db.delete(membership)
    await db.commit()


async def remove_room_member(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    room_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> None:
    """Remove a member while holding the same row lock used by message sends."""
    actor = await lock_membership_for_update(db, room_id, actor_id)
    if actor is None or actor.role != "owner":
        raise ApiError(403, "room_owner_required", "Room owner permission is required.")
    target = await lock_membership_for_update(db, room_id, target_user_id)
    if target is None:
        raise ApiError(404, "member_not_found", "The room member does not exist.")
    if target.role == "owner":
        raise ApiError(409, "owner_cannot_be_removed", "The room owner cannot be removed.")
    event_id = uuid.uuid4()
    db.add(
        Notification(
            user_id=target_user_id,
            type="room_membership_removed",
            room_id=room_id,
            actor_id=actor_id,
            dedup_key=f"member-removed:{event_id}",
            metadata_json={"room_id": str(room_id)},
        )
    )
    await db.delete(target)
    await db.commit()


async def delete_room(db: AsyncSession, context: AuthContext, room_id: uuid.UUID) -> None:
    room = await db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if room is None:
        raise ApiError(404, "room_not_found", "The room does not exist.")
    membership = await lock_membership_for_update(db, room_id, context.user.id)
    if membership is None or membership.role != "owner":
        raise ApiError(403, "room_owner_required", "Room owner permission is required.")
    await db.delete(room)
    await db.commit()


async def list_joined_rooms(
    db: AsyncSession,
    context: AuthContext,
    *,
    cursor: Cursor | None,
    limit: int,
) -> JoinedRoomPage:
    statement = (
        select(Room, RoomMembership.role, RoomMembership.joined_at)
        .join(RoomMembership, RoomMembership.room_id == Room.id)
        .where(RoomMembership.user_id == context.user.id)
        .order_by(RoomMembership.joined_at.desc(), RoomMembership.room_id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        statement = statement.where(
            tuple_(RoomMembership.joined_at, RoomMembership.room_id)
            < tuple_(cursor.timestamp, cursor.item_id)
        )
    rows = (await db.execute(statement)).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [
        JoinedRoom(
            room=_room_view(row[0], row[1], row[2]),
            role=row[1],
            joined_at=row[2],
        )
        for row in page_rows
    ]
    next_cursor = None
    if has_more and page_rows:
        next_cursor = encode_cursor(page_rows[-1][2], page_rows[-1][0].id)
    return JoinedRoomPage(items=items, next_cursor=next_cursor)


def _invitation_view(
    invitation: RoomInvitation, room: Room, inviter: User, invitee: User
) -> InvitationView:
    return InvitationView(
        id=invitation.id,
        room_id=invitation.room_id,
        room_name=room.name,
        inviter_username=inviter.username,
        invitee_username=invitee.username,
        status=invitation.status,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        responded_at=invitation.responded_at,
    )


async def create_invitation(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    data: InviteUserRequest,
    *,
    lifetime_days: int,
) -> tuple[InvitationView, uuid.UUID]:
    actor = await lock_membership_for_update(db, room_id, context.user.id)
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None or (room.visibility == "private" and actor is None):
        raise ApiError(404, "room_not_found", "The room does not exist.")
    if actor is None or actor.role != "owner":
        raise ApiError(403, "room_owner_required", "Room owner permission is required.")
    invitee = await db.scalar(select(User).where(func.lower(User.username) == data.username))
    if invitee is None:
        raise ApiError(404, "user_not_found", "The user does not exist.")
    if invitee.id == context.user.id:
        raise ApiError(409, "cannot_invite_self", "You cannot invite yourself.")
    if await db.scalar(
        select(RoomMembership).where(
            RoomMembership.room_id == room_id, RoomMembership.user_id == invitee.id
        )
    ):
        raise ApiError(409, "already_a_member", "That user is already a room member.")
    invitation = RoomInvitation(
        room_id=room_id,
        inviter_id=context.user.id,
        invitee_id=invitee.id,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=lifetime_days),
    )
    db.add(invitation)
    try:
        await db.flush()
        db.add(
            Notification(
                user_id=invitee.id,
                type="room_invitation",
                room_id=room_id,
                actor_id=context.user.id,
                invitation_id=invitation.id,
                dedup_key=f"invitation:{invitation.id}",
                metadata_json={"invitation_id": str(invitation.id)},
            )
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ApiError(409, "invitation_pending", "A pending invitation already exists.") from None
    await db.refresh(invitation)
    return _invitation_view(invitation, room, context.user, invitee), invitee.id


async def list_invitations(
    db: AsyncSession, context: AuthContext, *, cursor: Cursor | None, limit: int
) -> InvitationPage:
    inviter = aliased(User, name="inviter")
    invitee = aliased(User, name="invitee")
    statement = (
        select(RoomInvitation, Room, inviter, invitee)
        .join(Room, Room.id == RoomInvitation.room_id)
        .join(inviter, inviter.id == RoomInvitation.inviter_id)
        .join(invitee, invitee.id == RoomInvitation.invitee_id)
        .where(RoomInvitation.invitee_id == context.user.id, RoomInvitation.status == "pending")
        .order_by(RoomInvitation.created_at.desc(), RoomInvitation.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        statement = statement.where(
            tuple_(RoomInvitation.created_at, RoomInvitation.id)
            < tuple_(cursor.timestamp, cursor.item_id)
        )
    rows = (await db.execute(statement)).all()
    page = rows[:limit]
    now = datetime.now(UTC)
    items: list[InvitationView] = []
    for invitation, room, inviter_row, invitee_row in page:
        if invitation.expires_at <= now:
            invitation.status = "expired"
            invitation.responded_at = now
            continue
        items.append(
            InvitationView(
                id=invitation.id,
                room_id=invitation.room_id,
                room_name=room.name,
                inviter_username=inviter_row.username,
                invitee_username=invitee_row.username,
                status=invitation.status,
                created_at=invitation.created_at,
                expires_at=invitation.expires_at,
                responded_at=invitation.responded_at,
            )
        )
    if db.dirty:
        await db.commit()
    next_cursor = None
    if len(rows) > limit and page:
        next_cursor = encode_cursor(page[-1][0].created_at, page[-1][0].id)
    return InvitationPage(items=items, next_cursor=next_cursor)


async def list_room_invitations(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    *,
    cursor: Cursor | None,
    limit: int,
) -> InvitationPage:
    """List every invitation for a room, visible only to its current owner."""
    owner = await db.scalar(
        select(RoomMembership).where(
            RoomMembership.room_id == room_id,
            RoomMembership.user_id == context.user.id,
        )
    )
    if owner is None or owner.role != "owner":
        raise ApiError(403, "room_owner_required", "Room owner permission is required.")

    inviter = aliased(User, name="sent_inviter")
    invitee = aliased(User, name="sent_invitee")
    statement = (
        select(RoomInvitation, Room, inviter, invitee)
        .join(Room, Room.id == RoomInvitation.room_id)
        .join(inviter, inviter.id == RoomInvitation.inviter_id)
        .join(invitee, invitee.id == RoomInvitation.invitee_id)
        .where(RoomInvitation.room_id == room_id)
        .order_by(RoomInvitation.created_at.desc(), RoomInvitation.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        statement = statement.where(
            tuple_(RoomInvitation.created_at, RoomInvitation.id)
            < tuple_(cursor.timestamp, cursor.item_id)
        )
    rows = (await db.execute(statement)).all()
    page = rows[:limit]
    now = datetime.now(UTC)
    items: list[InvitationView] = []
    for invitation, room, inviter_row, invitee_row in page:
        if invitation.status == "pending" and invitation.expires_at <= now:
            invitation.status = "expired"
            invitation.responded_at = now
        items.append(_invitation_view(invitation, room, inviter_row, invitee_row))
    if db.dirty:
        await db.commit()

    next_cursor = None
    if len(rows) > limit and page:
        next_cursor = encode_cursor(page[-1][0].created_at, page[-1][0].id)
    return InvitationPage(items=items, next_cursor=next_cursor)


async def respond_to_invitation(
    db: AsyncSession,
    context: AuthContext,
    invitation_id: uuid.UUID,
    *,
    accept: bool,
) -> tuple[InvitationView, uuid.UUID | None]:
    invitation = await db.scalar(
        select(RoomInvitation)
        .where(RoomInvitation.id == invitation_id, RoomInvitation.invitee_id == context.user.id)
        .with_for_update()
    )
    if invitation is None:
        raise ApiError(404, "invitation_not_found", "The invitation does not exist.")
    room = await db.get(Room, invitation.room_id)
    if room is None:
        raise ApiError(404, "invitation_not_found", "The invitation does not exist.")
    inviter = await db.get(User, invitation.inviter_id)
    if inviter is None:
        raise ApiError(404, "invitation_not_found", "The invitation does not exist.")
    now = datetime.now(UTC)
    if invitation.status != "pending":
        raise ApiError(409, "invitation_not_pending", "The invitation is no longer pending.")
    if invitation.expires_at <= now:
        invitation.status = "expired"
        invitation.responded_at = now
        await db.commit()
        raise ApiError(409, "invitation_expired", "The invitation has expired.")
    invitation.status = "accepted" if accept else "declined"
    invitation.responded_at = now
    if accept:
        db.add(RoomMembership(user_id=context.user.id, room_id=room.id, role="member"))
    await db.commit()
    await db.refresh(invitation)
    return _invitation_view(invitation, room, inviter, context.user), room.id if accept else None


async def revoke_invitation(
    db: AsyncSession, context: AuthContext, room_id: uuid.UUID, invitation_id: uuid.UUID
) -> InvitationView:
    actor = await lock_membership_for_update(db, room_id, context.user.id)
    if actor is None or actor.role != "owner":
        raise ApiError(403, "room_owner_required", "Room owner permission is required.")
    invitation = await db.scalar(
        select(RoomInvitation)
        .where(RoomInvitation.id == invitation_id, RoomInvitation.room_id == room_id)
        .with_for_update()
    )
    if invitation is None:
        raise ApiError(404, "invitation_not_found", "The invitation does not exist.")
    if invitation.status != "pending":
        raise ApiError(409, "invitation_not_pending", "The invitation is no longer pending.")
    invitation.status = "revoked"
    invitation.responded_at = datetime.now(UTC)
    room = await db.get(Room, room_id)
    invitee = await db.get(User, invitation.invitee_id)
    await db.commit()
    assert room is not None and invitee is not None
    return _invitation_view(invitation, room, context.user, invitee)


async def list_room_members(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    *,
    cursor: Cursor | None,
    limit: int,
    online_user_ids: set[uuid.UUID],
) -> MemberPage:
    membership = await db.scalar(
        select(RoomMembership).where(
            RoomMembership.room_id == room_id, RoomMembership.user_id == context.user.id
        )
    )
    room = await db.get(Room, room_id)
    if room is None or (room.visibility == "private" and membership is None):
        raise ApiError(404, "room_not_found", "The room does not exist.")
    if membership is None:
        raise ApiError(403, "room_membership_required", "You are not a room member.")
    statement = (
        select(RoomMembership, User)
        .join(User, User.id == RoomMembership.user_id)
        .where(RoomMembership.room_id == room_id)
        .order_by(RoomMembership.joined_at.desc(), RoomMembership.user_id.desc())
        .limit(limit + 1)
    )
    if cursor:
        statement = statement.where(
            tuple_(RoomMembership.joined_at, RoomMembership.user_id)
            < tuple_(cursor.timestamp, cursor.item_id)
        )
    rows = (await db.execute(statement)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        next_cursor = encode_cursor(page[-1][0].joined_at, page[-1][0].user_id)
    return MemberPage(
        items=[
            MemberView(
                user_id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=item.role,
                joined_at=item.joined_at,
                online=user.id in online_user_ids,
                last_seen_at=user.last_seen_at,
            )
            for item, user in page
        ],
        next_cursor=next_cursor,
    )
