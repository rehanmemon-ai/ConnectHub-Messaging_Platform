import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, insert, inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthSession, Message, Room, RoomMembership, User
from app.queries.messages import MessageCursor, build_message_history_query

pytestmark = pytest.mark.integration


def user(username: str, email: str) -> User:
    return User(
        username=username,
        email=email,
        password_hash="argon2id-placeholder-not-a-real-password",
        display_name=username,
    )


async def persist_user(
    session: AsyncSession, username: str = "alice", email: str = "a@test"
) -> User:
    model = user(username, email)
    session.add(model)
    await session.commit()
    return model


async def persist_room(session: AsyncSession, name: str = "Python Lounge") -> Room:
    model = Room(name=name, description="A room")
    session.add(model)
    await session.commit()
    return model


async def test_user_uuid_and_case_insensitive_uniqueness(db_session: AsyncSession) -> None:
    first = await persist_user(db_session)
    assert isinstance(first.id, uuid.UUID)

    db_session.add(user("ALICE", "other@test"))
    with pytest.raises(DBAPIError):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(user("bob", "A@TEST"))
    with pytest.raises(DBAPIError):
        await db_session.commit()


async def test_user_required_columns_reject_null(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(User).values(
                username=None,
                email="a@test",
                password_hash="placeholder",
                display_name="Alice",
            )
        )
        await db_session.commit()


@pytest.mark.parametrize(
    ("field", "value"),
    [("username", ""), ("username", "x" * 51), ("display_name", " ")],
)
async def test_user_required_lengths_are_enforced(
    db_session: AsyncSession, field: str, value: str
) -> None:
    model = user("alice", "a@test")
    setattr(model, field, value)
    db_session.add(model)
    with pytest.raises(DBAPIError):
        await db_session.commit()


async def test_session_digest_expiry_and_user_cascade(db_session: AsyncSession) -> None:
    owner = await persist_user(db_session)
    owner_id = owner.id
    now = datetime.now(UTC)
    session = AuthSession(
        user_id=owner_id,
        token_hash="a" * 64,
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(session)
    await db_session.commit()

    db_session.add(
        AuthSession(
            user_id=owner_id,
            token_hash="a" * 64,
            created_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    await db_session.execute(delete(User).where(User.id == owner_id))
    await db_session.commit()
    assert (
        await db_session.scalar(select(AuthSession.id).where(AuthSession.user_id == owner_id))
        is None
    )


async def test_session_rejects_invalid_digest_and_expiry(db_session: AsyncSession) -> None:
    owner = await persist_user(db_session)
    now = datetime.now(UTC)
    db_session.add(
        AuthSession(
            user_id=owner.id,
            token_hash="not-sha256",
            created_at=now,
            expires_at=now - timedelta(seconds=1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_session_rejects_unknown_user(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    db_session.add(
        AuthSession(
            user_id=uuid.uuid4(),
            token_hash="b" * 64,
            created_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_rooms_allow_duplicate_names_and_generate_uuids(db_session: AsyncSession) -> None:
    first = Room(name="General", description="First")
    second = Room(name="General", description="Second")
    db_session.add_all([first, second])
    await db_session.commit()
    assert isinstance(first.id, uuid.UUID)
    assert isinstance(second.id, uuid.UUID)
    assert first.id != second.id


async def test_database_permits_zero_owner_room_as_documented_limitation(
    db_session: AsyncSession,
) -> None:
    room = await persist_room(db_session)
    assert (
        await db_session.scalar(
            select(RoomMembership.room_id).where(RoomMembership.room_id == room.id)
        )
        is None
    )


async def test_membership_many_to_many_and_duplicate_pair(db_session: AsyncSession) -> None:
    alice = await persist_user(db_session)
    bob = await persist_user(db_session, "bob", "b@test")
    first = await persist_room(db_session)
    second = await persist_room(db_session, "Databases")
    db_session.add_all(
        [
            RoomMembership(user_id=alice.id, room_id=first.id, role="owner"),
            RoomMembership(user_id=alice.id, room_id=second.id, role="owner"),
            RoomMembership(user_id=bob.id, room_id=first.id, role="member"),
        ]
    )
    await db_session.commit()
    assert len((await db_session.scalars(select(RoomMembership))).all()) == 3

    db_session.add(RoomMembership(user_id=bob.id, room_id=first.id, role="member"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_membership_role_and_one_owner_per_room(db_session: AsyncSession) -> None:
    alice = await persist_user(db_session)
    bob = await persist_user(db_session, "bob", "b@test")
    room = await persist_room(db_session)
    bob_id = bob.id
    room_id = room.id
    db_session.add(RoomMembership(user_id=alice.id, room_id=room.id, role="owner"))
    await db_session.commit()

    db_session.add(RoomMembership(user_id=bob_id, room_id=room_id, role="owner"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(RoomMembership(user_id=bob_id, room_id=room_id, role="moderator"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_membership_restricts_user_delete(db_session: AsyncSession) -> None:
    alice = await persist_user(db_session)
    room = await persist_room(db_session)
    db_session.add(RoomMembership(user_id=alice.id, room_id=room.id, role="owner"))
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(delete(User).where(User.id == alice.id))
        await db_session.commit()


async def test_message_constraints_sender_restrict_and_room_cascade(
    db_session: AsyncSession,
) -> None:
    alice = await persist_user(db_session)
    room = await persist_room(db_session)
    message = Message(room_id=room.id, sender_id=alice.id, content="Hello")
    db_session.add(message)
    await db_session.commit()
    assert isinstance(message.id, uuid.UUID)
    alice_id = alice.id
    room_id = room.id
    message_id = message.id

    with pytest.raises(IntegrityError):
        await db_session.execute(delete(User).where(User.id == alice_id))
        await db_session.commit()
    await db_session.rollback()

    await db_session.execute(delete(Room).where(Room.id == room_id))
    await db_session.commit()
    assert await db_session.scalar(select(Message.id).where(Message.id == message_id)) is None


async def test_message_rejects_unknown_foreign_keys(db_session: AsyncSession) -> None:
    db_session.add(Message(room_id=uuid.uuid4(), sender_id=uuid.uuid4(), content="No parents"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.parametrize("content", ["", " ", "x" * 4001])
async def test_message_content_constraints(db_session: AsyncSession, content: str) -> None:
    alice = await persist_user(db_session)
    room = await persist_room(db_session)
    db_session.add(Message(room_id=room.id, sender_id=alice.id, content=content))
    with pytest.raises(DBAPIError):
        await db_session.commit()


async def test_room_deletion_cascades_memberships_and_messages(db_session: AsyncSession) -> None:
    alice = await persist_user(db_session)
    room = await persist_room(db_session)
    db_session.add_all(
        [
            RoomMembership(user_id=alice.id, room_id=room.id, role="owner"),
            Message(room_id=room.id, sender_id=alice.id, content="Persisted first"),
        ]
    )
    await db_session.commit()

    await db_session.execute(delete(Room).where(Room.id == room.id))
    await db_session.commit()
    assert await db_session.scalar(select(RoomMembership.room_id)) is None
    assert await db_session.scalar(select(Message.id)) is None


async def test_foreign_key_violation_rolls_back_transaction(db_session: AsyncSession) -> None:
    missing = uuid.uuid4()
    db_session.add(RoomMembership(user_id=missing, room_id=missing, role="member"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    assert await db_session.scalar(select(RoomMembership.room_id)) is None


async def test_history_index_exists(db_session: AsyncSession) -> None:
    connection = await db_session.connection()

    def index_names(sync_connection) -> set[str]:  # type: ignore[no-untyped-def]
        return {item["name"] for item in inspect(sync_connection).get_indexes("messages")}

    names = await connection.run_sync(index_names)
    assert "ix_messages_room_history" in names


async def test_history_query_orders_tied_timestamps_by_uuid(db_session: AsyncSession) -> None:
    alice = await persist_user(db_session)
    room = await persist_room(db_session)
    timestamp = datetime(2026, 11, 16, tzinfo=UTC)
    lower_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    higher_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    db_session.add_all(
        [
            Message(
                id=lower_id,
                room_id=room.id,
                sender_id=alice.id,
                content="First",
                created_at=timestamp,
            ),
            Message(
                id=higher_id,
                room_id=room.id,
                sender_id=alice.id,
                content="Second",
                created_at=timestamp,
            ),
        ]
    )
    await db_session.commit()

    newest = (await db_session.scalars(build_message_history_query(room.id, page_size=1))).all()
    assert [item.id for item in newest] == [higher_id, lower_id]

    older = (
        await db_session.scalars(
            build_message_history_query(
                room.id,
                before=MessageCursor(created_at=timestamp, message_id=higher_id),
                page_size=50,
            )
        )
    ).all()
    assert [item.id for item in older] == [lower_id]
