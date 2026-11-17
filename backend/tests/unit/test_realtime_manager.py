import asyncio
import uuid

from app.realtime.manager import ConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.closed: tuple[int, str] | None = None

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)

    async def close(self, code: int, reason: str) -> None:
        self.closed = (code, reason)


async def test_multi_connection_presence_and_room_isolation() -> None:
    manager = ConnectionManager()
    user_id, session_id, room_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    first_socket, second_socket, outsider_socket = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    first = await manager.register(
        first_socket, user_id=user_id, session_id=session_id, queue_size=10, connection_limit=3
    )
    second = await manager.register(
        second_socket, user_id=user_id, session_id=session_id, queue_size=10, connection_limit=3
    )
    outsider = await manager.register(
        outsider_socket,
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        queue_size=10,
        connection_limit=3,
    )
    await manager.subscribe(first, room_id)
    await manager.subscribe(second, room_id)
    assert await manager.room_user_connection_count(room_id, user_id) == 2
    await manager.broadcast_room(room_id, {"type": "room.event"})
    await asyncio.sleep(0)

    assert first_socket.events == second_socket.events == [{"type": "room.event"}]
    assert outsider_socket.events == []
    assert await manager.user_connection_count(user_id) == 2
    assert await manager.disconnect(first)
    assert await manager.user_connection_count(user_id) == 1
    assert await manager.room_user_connection_count(room_id, user_id) == 1
    assert not await manager.disconnect(second)
    assert await manager.room_user_connection_count(room_id, user_id) == 0
    await manager.disconnect(outsider)


async def test_session_revocation_disconnects_every_device() -> None:
    manager = ConnectionManager()
    user_id, session_id = uuid.uuid4(), uuid.uuid4()
    sockets = [FakeWebSocket(), FakeWebSocket()]
    for socket in sockets:
        await manager.register(
            socket, user_id=user_id, session_id=session_id, queue_size=10, connection_limit=2
        )

    await manager.disconnect_session(session_id)

    assert await manager.user_connection_count(user_id) == 0
    assert all(socket.closed == (4001, "session_revoked") for socket in sockets)


async def test_typing_expires_and_slow_client_is_disconnected() -> None:
    manager = ConnectionManager()
    room_id = uuid.uuid4()
    sender_socket, observer_socket = FakeWebSocket(), FakeWebSocket()
    sender = await manager.register(
        sender_socket,
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        queue_size=10,
        connection_limit=1,
    )
    observer = await manager.register(
        observer_socket,
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        queue_size=10,
        connection_limit=1,
    )
    await manager.subscribe(sender, room_id)
    await manager.subscribe(observer, room_id)
    await manager.start_typing(sender, room_id, {"type": "typing.started"}, expiry_seconds=0)
    await asyncio.sleep(0.01)
    assert [event["type"] for event in observer_socket.events] == [
        "typing.started",
        "typing.stopped",
    ]

    slow_socket = FakeWebSocket()
    slow = await manager.register(
        slow_socket,
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        queue_size=1,
        connection_limit=1,
    )
    assert slow.writer is not None
    slow.writer.cancel()
    await asyncio.sleep(0)
    assert await manager.enqueue(slow, {"type": "first"})
    assert not await manager.enqueue(slow, {"type": "overflow"})
    assert slow_socket.closed == (1013, "slow_client")
    await manager.shutdown()
