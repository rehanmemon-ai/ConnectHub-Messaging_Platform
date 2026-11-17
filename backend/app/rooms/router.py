import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.identity.dependencies import AppSettings, CurrentAuth, DatabaseSession
from app.realtime.manager import connection_manager
from app.rooms.cursors import decode_cursor
from app.rooms.schemas import (
    CreateRoomRequest,
    InvitationEnvelope,
    InvitationPage,
    InviteUserRequest,
    JoinedRoomPage,
    MemberPage,
    MembershipEnvelope,
    RoomEnvelope,
    RoomPage,
)
from app.rooms.service import (
    create_invitation,
    create_room,
    delete_room,
    get_room,
    join_room,
    leave_room,
    list_invitations,
    list_joined_rooms,
    list_public_rooms,
    list_room_invitations,
    list_room_members,
    remove_room_member,
    respond_to_invitation,
    revoke_invitation,
)
from app.security.http import require_csrf
from app.security.rate_limit import rate_limiter

rooms_router = APIRouter(prefix="/api/v1/rooms", tags=["rooms"])
user_rooms_router = APIRouter(prefix="/api/v1/users", tags=["rooms"])
invitations_router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])


def _client_key(request: Request, operation: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{operation}:{host}"


@rooms_router.get("", response_model=RoomPage)
async def discover_rooms(
    context: CurrentAuth,
    db: DatabaseSession,
    search: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoomPage:
    normalized_search = search.strip() if search else None
    return await list_public_rooms(
        db,
        context,
        search=normalized_search,
        cursor=decode_cursor(cursor),
        limit=limit,
    )


@rooms_router.post("", status_code=201, response_model=RoomEnvelope)
async def post_room(
    data: CreateRoomRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> RoomEnvelope:
    require_csrf(request, context.session, settings)
    await rate_limiter.check(
        _client_key(request, "room-create"),
        limit=settings.room_create_rate_limit,
        window_seconds=settings.rate_limit_window_seconds,
    )
    return RoomEnvelope(room=await create_room(db, context, data))


@rooms_router.get("/{room_id}", response_model=RoomEnvelope)
async def room_detail(
    room_id: uuid.UUID, context: CurrentAuth, db: DatabaseSession
) -> RoomEnvelope:
    return RoomEnvelope(room=await get_room(db, context, room_id))


@rooms_router.post("/{room_id}/membership", status_code=201, response_model=MembershipEnvelope)
async def post_membership(
    room_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> MembershipEnvelope:
    require_csrf(request, context.session, settings)
    return MembershipEnvelope(membership=await join_room(db, context, room_id))


@rooms_router.delete("/{room_id}/membership", status_code=status.HTTP_204_NO_CONTENT)
async def delete_membership(
    room_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> Response:
    require_csrf(request, context.session, settings)
    await leave_room(db, context, room_id)
    await connection_manager.disconnect_room_user(room_id, context.user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@rooms_router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_owned_room(
    room_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> Response:
    require_csrf(request, context.session, settings)
    await delete_room(db, context, room_id)
    await connection_manager.disconnect_room(room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@user_rooms_router.get("/me/rooms", response_model=JoinedRoomPage)
async def my_rooms(
    context: CurrentAuth,
    db: DatabaseSession,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JoinedRoomPage:
    return await list_joined_rooms(
        db,
        context,
        cursor=decode_cursor(cursor),
        limit=limit,
    )


@rooms_router.get("/{room_id}/members", response_model=MemberPage)
async def room_members(
    room_id: uuid.UUID,
    context: CurrentAuth,
    db: DatabaseSession,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MemberPage:
    return await list_room_members(
        db,
        context,
        room_id,
        cursor=decode_cursor(cursor),
        limit=limit,
        online_user_ids=await connection_manager.online_user_ids(),
    )


@rooms_router.delete("/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_member(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> Response:
    require_csrf(request, context.session, settings)
    await remove_room_member(db, actor_id=context.user.id, room_id=room_id, target_user_id=user_id)
    await connection_manager.disconnect_room_user(room_id, user_id)
    await connection_manager.broadcast_user(
        user_id, {"type": "notification.created", "notification_type": "room_membership_removed"}
    )
    await connection_manager.broadcast_room(
        room_id, {"type": "room.member_removed", "room_id": str(room_id), "user_id": str(user_id)}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@rooms_router.post("/{room_id}/invitations", status_code=201, response_model=InvitationEnvelope)
async def post_invitation(
    room_id: uuid.UUID,
    data: InviteUserRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> InvitationEnvelope:
    require_csrf(request, context.session, settings)
    invitation, invitee_id = await create_invitation(
        db,
        context,
        room_id,
        data,
        lifetime_days=settings.invitation_lifetime_days,
    )
    await connection_manager.broadcast_user(
        invitee_id,
        {
            "type": "notification.created",
            "notification_type": "room_invitation",
            "invitation_id": str(invitation.id),
        },
    )
    return InvitationEnvelope(invitation=invitation)


@rooms_router.get("/{room_id}/invitations", response_model=InvitationPage)
async def room_invitations(
    room_id: uuid.UUID,
    context: CurrentAuth,
    db: DatabaseSession,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> InvitationPage:
    return await list_room_invitations(
        db,
        context,
        room_id,
        cursor=decode_cursor(cursor),
        limit=limit,
    )


@rooms_router.delete("/{room_id}/invitations/{invitation_id}", response_model=InvitationEnvelope)
async def delete_invitation(
    room_id: uuid.UUID,
    invitation_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> InvitationEnvelope:
    require_csrf(request, context.session, settings)
    return InvitationEnvelope(
        invitation=await revoke_invitation(db, context, room_id, invitation_id)
    )


@user_rooms_router.get("/me/invitations", response_model=InvitationPage)
async def my_invitations(
    context: CurrentAuth,
    db: DatabaseSession,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> InvitationPage:
    return await list_invitations(db, context, cursor=decode_cursor(cursor), limit=limit)


@invitations_router.post("/{invitation_id}/accept", response_model=InvitationEnvelope)
async def accept_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> InvitationEnvelope:
    require_csrf(request, context.session, settings)
    invitation, room_id = await respond_to_invitation(db, context, invitation_id, accept=True)
    assert room_id is not None
    await connection_manager.broadcast_room(
        room_id,
        {"type": "room.member_joined", "room_id": str(room_id), "user_id": str(context.user.id)},
    )
    return InvitationEnvelope(invitation=invitation)


@invitations_router.post("/{invitation_id}/decline", response_model=InvitationEnvelope)
async def decline_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: AppSettings,
) -> InvitationEnvelope:
    require_csrf(request, context.session, settings)
    invitation, _ = await respond_to_invitation(db, context, invitation_id, accept=False)
    return InvitationEnvelope(invitation=invitation)
