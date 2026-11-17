import asyncio
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

from app.realtime.manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, close_error: Exception | None = None) -> None:
        self.events: list[dict[str, object]] = []
        self.closed: tuple[int, str] | None = None
        self.close_error = close_error

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)

    async def close(self, code: int, reason: str) -> None:
        self.closed = (code, reason)
        if self.close_error is not None:
            raise self.close_error


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


async def test_disconnect_is_idempotent_and_tolerates_an_already_closed_socket() -> None:
    manager = ConnectionManager()
    socket = FakeWebSocket(WebSocketDisconnect(code=1006))
    connection = await manager.register(
        socket,
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        queue_size=10,
        connection_limit=1,
    )
    room_id = uuid.uuid4()
    await manager.subscribe(connection, room_id)
    await manager.start_typing(connection, room_id, {"type": "typing.started"}, 60)

    assert not await manager.disconnect(connection)
    assert not await manager.disconnect(connection)
    assert await manager.user_connection_count(connection.user_id) == 0
    assert connection.writer is not None and connection.writer.done()
    assert manager._typing_tasks == {}


async def test_disconnect_does_not_hide_unexpected_close_errors() -> None:
    manager = ConnectionManager()
    connection = await manager.register(
        FakeWebSocket(ValueError("programmer error")),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        queue_size=10,
        connection_limit=1,
    )

    with pytest.raises(ValueError, match="programmer error"):
        await manager.disconnect(connection)
    assert await manager.user_connection_count(connection.user_id) == 0
