import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class Connection:
    id: uuid.UUID
    websocket: WebSocket
    user_id: uuid.UUID
    session_id: uuid.UUID
    queue: asyncio.Queue[tuple[dict[str, Any], asyncio.Future[None] | None]]
    subscriptions: set[uuid.UUID] = field(default_factory=set)
    writer: asyncio.Task[None] | None = None


class ConnectionManager:
    """Bounded single-process socket registry.

    PostgreSQL remains authoritative. This registry intentionally provides no
    cross-process broadcast or presence guarantee.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, Connection] = {}
        self._lock = asyncio.Lock()
        self._typing_tasks: dict[tuple[uuid.UUID, uuid.UUID], asyncio.Task[None]] = {}

    async def register(
        self,
        websocket: WebSocket,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        queue_size: int,
        connection_limit: int,
    ) -> Connection:
        async with self._lock:
            current = sum(item.user_id == user_id for item in self._connections.values())
            if current >= connection_limit:
                raise RuntimeError("connection_limit")
            connection = Connection(
                id=uuid.uuid4(),
                websocket=websocket,
                user_id=user_id,
                session_id=session_id,
                queue=asyncio.Queue(maxsize=queue_size),
            )
            self._connections[connection.id] = connection
            connection.writer = asyncio.create_task(self._writer(connection))
            return connection

    async def _writer(self, connection: Connection) -> None:
        try:
            while True:
                event, delivered = await connection.queue.get()
                try:
                    await connection.websocket.send_json(event)
                except Exception as error:
                    if delivered is not None and not delivered.done():
                        delivered.set_exception(error)
                    raise
                if delivered is not None and not delivered.done():
                    delivered.set_result(None)
        except (asyncio.CancelledError, RuntimeError):
            return

    async def enqueue(self, connection: Connection, event: dict[str, Any]) -> bool:
        try:
            connection.queue.put_nowait((event, None))
            return True
        except asyncio.QueueFull:
            await self.disconnect(connection, code=1013, reason="slow_client")
            return False

    async def enqueue_and_wait(self, connection: Connection, event: dict[str, Any]) -> bool:
        delivered = asyncio.get_running_loop().create_future()
        try:
            connection.queue.put_nowait((event, delivered))
        except asyncio.QueueFull:
            await self.disconnect(connection, code=1013, reason="slow_client")
            return False
        try:
            await delivered
        except (RuntimeError, asyncio.CancelledError):
            return False
        return True

    async def subscribe(self, connection: Connection, room_id: uuid.UUID) -> None:
        async with self._lock:
            if connection.id in self._connections:
                connection.subscriptions.add(room_id)

    async def unsubscribe(self, connection: Connection, room_id: uuid.UUID) -> None:
        await self.stop_typing(connection, room_id)
        async with self._lock:
            connection.subscriptions.discard(room_id)

    async def broadcast_room(self, room_id: uuid.UUID, event: dict[str, Any]) -> None:
        async with self._lock:
            targets = [item for item in self._connections.values() if room_id in item.subscriptions]
        for connection in targets:
            await self.enqueue(connection, event)

    async def broadcast_user(self, user_id: uuid.UUID, event: dict[str, Any]) -> None:
        async with self._lock:
            targets = [item for item in self._connections.values() if item.user_id == user_id]
        for connection in targets:
            await self.enqueue(connection, event)

    async def disconnect(
        self, connection: Connection, *, code: int = 1000, reason: str = "closed"
    ) -> bool:
        async with self._lock:
            removed = self._connections.pop(connection.id, None)
            remaining_online = any(
                item.user_id == connection.user_id for item in self._connections.values()
            )
        if removed is None:
            return remaining_online
        for room_id in tuple(connection.subscriptions):
            await self.stop_typing(connection, room_id)
        current = asyncio.current_task()
        if connection.writer is not None and connection.writer is not current:
            connection.writer.cancel()
        try:
            await connection.websocket.close(code=code, reason=reason)
        except RuntimeError:
            pass
        return remaining_online

    async def disconnect_session(self, session_id: uuid.UUID) -> None:
        async with self._lock:
            targets = [item for item in self._connections.values() if item.session_id == session_id]
        for connection in targets:
            await self.disconnect(connection, code=4001, reason="session_revoked")

    async def disconnect_room_user(self, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with self._lock:
            targets = [
                item
                for item in self._connections.values()
                if item.user_id == user_id and room_id in item.subscriptions
            ]
        for connection in targets:
            await self.unsubscribe(connection, room_id)
            await self.enqueue(
                connection,
                {"type": "room.membership_removed", "room_id": str(room_id)},
            )

    async def disconnect_room(self, room_id: uuid.UUID) -> None:
        async with self._lock:
            targets = [item for item in self._connections.values() if room_id in item.subscriptions]
        for connection in targets:
            await self.unsubscribe(connection, room_id)
            await self.enqueue(connection, {"type": "room.deleted", "room_id": str(room_id)})

    async def user_connection_count(self, user_id: uuid.UUID) -> int:
        async with self._lock:
            return sum(item.user_id == user_id for item in self._connections.values())

    async def room_user_connection_count(self, room_id: uuid.UUID, user_id: uuid.UUID) -> int:
        async with self._lock:
            return sum(
                item.user_id == user_id and room_id in item.subscriptions
                for item in self._connections.values()
            )

    async def online_user_ids(self) -> set[uuid.UUID]:
        async with self._lock:
            return {item.user_id for item in self._connections.values()}

    async def start_typing(
        self,
        connection: Connection,
        room_id: uuid.UUID,
        event: dict[str, Any],
        expiry_seconds: int,
    ) -> None:
        key = (connection.id, room_id)
        previous = self._typing_tasks.pop(key, None)
        if previous is not None:
            previous.cancel()
        await self.broadcast_room(room_id, event)

        async def expire() -> None:
            try:
                await asyncio.sleep(expiry_seconds)
                await self.broadcast_room(
                    room_id,
                    {
                        "type": "typing.stopped",
                        "room_id": str(room_id),
                        "user_id": str(connection.user_id),
                    },
                )
            finally:
                self._typing_tasks.pop(key, None)

        self._typing_tasks[key] = asyncio.create_task(expire())

    async def stop_typing(self, connection: Connection, room_id: uuid.UUID) -> None:
        task = self._typing_tasks.pop((connection.id, room_id), None)
        if task is not None:
            task.cancel()
            await self.broadcast_room(
                room_id,
                {
                    "type": "typing.stopped",
                    "room_id": str(room_id),
                    "user_id": str(connection.user_id),
                },
            )

    async def shutdown(self) -> None:
        async with self._lock:
            targets = list(self._connections.values())
        for connection in targets:
            await self.disconnect(connection, code=1001, reason="server_shutdown")

    async def clear(self) -> None:
        await self.shutdown()
        self._connections.clear()
        self._typing_tasks.clear()


connection_manager = ConnectionManager()
