import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.errors import ApiError
from app.core.config import Settings
from app.identity.service import AuthContext
from app.main import app
from app.messaging.schemas import SendMessageRequest
from app.messaging.service import send_message
from app.models import AuthSession, Message, Room, RoomMembership, User
from app.rooms.schemas import CreateRoomRequest
from app.rooms.service import create_room, lock_membership_for_update, remove_room_member

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://localhost:5173"}
PASSWORD = "correct horse battery staple"


async def register_and_login(client: AsyncClient, username: str, email: str) -> dict[str, str]:
    registered = await client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "username": username,
            "email": email,
            "password": PASSWORD,
            "display_name": username.title(),
        },
    )
    assert registered.status_code == 201
    logged_in = await client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"identifier": username, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    return {**ORIGIN, "X-CSRF-Token": client.cookies["connecthub_csrf"]}


async def create_api_room(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "Python Lounge",
    description: str = "Python learners",
):
    return await client.post(
        "/api/v1/rooms",
        headers=headers,
        json={"name": name, "description": description},
    )


async def test_room_creation_is_atomic_and_creator_is_owner(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    response = await create_api_room(api_client, headers)

    assert response.status_code == 201
    room = response.json()["room"]
    assert room["membership"]["role"] == "owner"
    stored = await db_session.scalar(
        select(RoomMembership).where(RoomMembership.room_id == uuid.UUID(room["id"]))
    )
    assert stored is not None and stored.role == "owner"


async def test_failed_owner_membership_flush_rolls_back_room(
    api_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    await register_and_login(api_client, "alice", "alice@example.test")
    user = await db_session.scalar(select(User).where(User.username == "alice"))
    assert user is not None
    fake_session = AuthSession(
        user_id=user.id,
        token_hash="f" * 64,
        created_at=datetime.now(UTC),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    context = AuthContext(user=user, session=fake_session)
    original_flush = db_session.flush
    calls = 0

    async def fail_second_flush(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated membership insert failure")
        return await original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", fail_second_flush)
    with pytest.raises(RuntimeError, match="simulated membership"):
        await create_room(db_session, context, CreateRoomRequest(name="Atomic", description=""))
    assert await db_session.scalar(select(func.count()).select_from(Room)) == 0


async def test_public_discovery_search_cursor_and_validation(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    first = (await create_api_room(api_client, headers, "100% Python")).json()["room"]
    second = (await create_api_room(api_client, headers, "1000 Python")).json()["room"]
    third = (await create_api_room(api_client, headers, "Databases")).json()["room"]
    tied = datetime(2026, 11, 16, tzinfo=UTC)
    rooms = (await db_session.scalars(select(Room))).all()
    for room in rooms:
        room.created_at = tied
    await db_session.commit()

    page = await api_client.get("/api/v1/rooms", params={"limit": 2})
    assert page.status_code == 200
    expected = sorted([first["id"], second["id"], third["id"]], reverse=True)
    assert [item["id"] for item in page.json()["items"]] == expected[:2]
    assert page.json()["next_cursor"] is not None
    next_page = await api_client.get(
        "/api/v1/rooms", params={"limit": 2, "cursor": page.json()["next_cursor"]}
    )
    assert [item["id"] for item in next_page.json()["items"]] == expected[2:]

    literal_percent = await api_client.get("/api/v1/rooms", params={"search": "%"})
    assert [item["name"] for item in literal_percent.json()["items"]] == ["100% Python"]
    assert (await api_client.get("/api/v1/rooms", params={"cursor": "bad"})).status_code == 400
    assert (await api_client.get("/api/v1/rooms", params={"limit": 101})).status_code == 422


async def test_join_leave_owner_rules_and_owner_delete_cascade(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    alice_headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_response = await create_api_room(api_client, alice_headers)
    room_id = room_response.json()["room"]["id"]
    alice_cookies = dict(api_client.cookies)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:5173") as bob:
        bob_headers = await register_and_login(bob, "bob", "bob@example.test")
        joined = await bob.post(f"/api/v1/rooms/{room_id}/membership", headers=bob_headers)
        duplicate = await bob.post(f"/api/v1/rooms/{room_id}/membership", headers=bob_headers)
        assert joined.status_code == 201
        assert duplicate.status_code == 409

        forbidden_delete = await bob.delete(f"/api/v1/rooms/{room_id}", headers=bob_headers)
        assert forbidden_delete.status_code == 403
        left = await bob.delete(f"/api/v1/rooms/{room_id}/membership", headers=bob_headers)
        assert left.status_code == 204

    api_client.cookies.clear()
    for name, value in alice_cookies.items():
        api_client.cookies.set(name, value)
    owner_leave = await api_client.delete(
        f"/api/v1/rooms/{room_id}/membership", headers=alice_headers
    )
    assert owner_leave.status_code == 409

    alice = await db_session.scalar(select(User).where(User.username == "alice"))
    assert alice is not None
    db_session.add(Message(room_id=uuid.UUID(room_id), sender_id=alice.id, content="Will cascade"))
    await db_session.commit()
    deleted = await api_client.delete(f"/api/v1/rooms/{room_id}", headers=alice_headers)
    assert deleted.status_code == 204
    assert await db_session.scalar(select(Room.id).where(Room.id == uuid.UUID(room_id))) is None
    assert await db_session.scalar(select(Message.id)) is None
    assert await db_session.scalar(select(RoomMembership.room_id)) is None


async def test_user_rooms_are_stably_paginated(api_client: AsyncClient) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    created = []
    for name in ("One", "Two", "Three"):
        created.append((await create_api_room(api_client, headers, name)).json()["room"]["id"])

    page = await api_client.get("/api/v1/users/me/rooms", params={"limit": 2})
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["next_cursor"] is not None
    older = await api_client.get(
        "/api/v1/users/me/rooms",
        params={"limit": 2, "cursor": page.json()["next_cursor"]},
    )
    assert len(older.json()["items"]) == 1
    assert {item["room"]["id"] for item in page.json()["items"] + older.json()["items"]} == set(
        created
    )


async def test_owner_member_removal_service_preserves_owner(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    alice_headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_id = uuid.UUID((await create_api_room(api_client, alice_headers)).json()["room"]["id"])
    alice = await db_session.scalar(select(User).where(User.username == "alice"))
    assert alice is not None
    bob = User(
        username="bob",
        email="bob@example.test",
        password_hash="argon2-placeholder",
        display_name="Bob",
    )
    db_session.add(bob)
    await db_session.flush()
    db_session.add(RoomMembership(user_id=bob.id, room_id=room_id, role="member"))
    await db_session.commit()

    await remove_room_member(db_session, actor_id=alice.id, room_id=room_id, target_user_id=bob.id)
    assert (
        await db_session.scalar(
            select(RoomMembership).where(
                RoomMembership.room_id == room_id, RoomMembership.user_id == bob.id
            )
        )
        is None
    )
    with pytest.raises(Exception) as error:
        await remove_room_member(
            db_session, actor_id=alice.id, room_id=room_id, target_user_id=alice.id
        )
    assert getattr(error.value, "code", None) == "owner_cannot_be_removed"


async def test_membership_lock_conflicts_until_transaction_end(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    user = User(
        username="alice",
        email="alice@example.test",
        password_hash="argon2-placeholder",
        display_name="Alice",
    )
    room = Room(name="Locks", description="")
    db_session.add_all([user, room])
    await db_session.flush()
    membership = RoomMembership(user_id=user.id, room_id=room.id, role="member")
    db_session.add(membership)
    await db_session.commit()

    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as first, factory() as second:
        assert await lock_membership_for_update(first, room.id, user.id) is not None
        await second.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(DBAPIError):
            await lock_membership_for_update(second, room.id, user.id)
        await second.rollback()
        await first.rollback()
    await engine.dispose()


async def test_send_and_member_removal_have_deterministic_commit_order(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    owner = User(
        username="owner",
        email="owner@example.test",
        password_hash="argon2-placeholder",
        display_name="Owner",
    )
    member = User(
        username="member",
        email="member@example.test",
        password_hash="argon2-placeholder",
        display_name="Member",
    )
    room = Room(name="Ordering", description="")
    db_session.add_all([owner, member, room])
    await db_session.flush()
    db_session.add_all(
        [
            RoomMembership(user_id=owner.id, room_id=room.id, role="owner"),
            RoomMembership(user_id=member.id, room_id=room.id, role="member"),
        ]
    )
    await db_session.commit()
    owner_id, member_id, room_id = owner.id, member.id, room.id

    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sender, factory() as remover:
        sending_user = await sender.get(User, member_id)
        assert sending_user is not None
        context = AuthContext(
            user=sending_user,
            session=AuthSession(
                user_id=member_id,
                token_hash="a" * 64,
                created_at=datetime.now(UTC),
                expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            ),
        )
        sent = await send_message(
            sender,
            context,
            room_id,
            SendMessageRequest(client_id=uuid.uuid4(), content="Committed first"),
            Settings(),
        )
        await remove_room_member(
            remover, actor_id=owner_id, room_id=room_id, target_user_id=member_id
        )
        assert sent.created

    async with factory() as restore:
        restore.add(RoomMembership(user_id=member_id, room_id=room_id, role="member"))
        await restore.commit()
    async with factory() as remover, factory() as sender:
        await remove_room_member(
            remover, actor_id=owner_id, room_id=room_id, target_user_id=member_id
        )
        sending_user = await sender.get(User, member_id)
        assert sending_user is not None
        context = AuthContext(
            user=sending_user,
            session=AuthSession(
                user_id=member_id,
                token_hash="b" * 64,
                created_at=datetime.now(UTC),
                expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            ),
        )
        with pytest.raises(ApiError) as denied:
            await send_message(
                sender,
                context,
                room_id,
                SendMessageRequest(client_id=uuid.uuid4(), content="Removed first"),
                Settings(),
            )
        assert denied.value.code == "room_membership_required"

    await engine.dispose()
