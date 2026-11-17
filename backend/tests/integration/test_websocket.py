import asyncio
import importlib
import selectors
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models import AuthSession, Message, Room, RoomMembership, User
from app.realtime.manager import connection_manager
from app.security.http import session_token_digest

pytestmark = pytest.mark.integration


def selector_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


async def seed_socket_context(db: AsyncSession, suffix: str = "") -> tuple[str, uuid.UUID]:
    raw_token = f"websocket-test-session-token{suffix}"
    user = User(
        username=f"socket-user{suffix}",
        email=f"socket-user{suffix}@example.test",
        password_hash="argon2-placeholder",
        display_name="Socket User",
    )
    room = Room(name="Socket Room", description="")
    db.add_all([user, room])
    await db.flush()
    db.add_all(
        [
            RoomMembership(user_id=user.id, room_id=room.id, role="owner"),
            AuthSession(
                user_id=user.id,
                token_hash=session_token_digest(raw_token),
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        ]
    )
    await db.commit()
    return raw_token, room.id


async def test_authenticated_websocket_persists_and_broadcasts_message(
    db_session: AsyncSession, migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_token, room_id = await seed_socket_context(db_session)
    socket_engine = create_async_engine(migrated_database_url, pool_pre_ping=True)
    realtime_router = importlib.import_module("app.realtime.router")
    monkeypatch.setattr(realtime_router, "get_engine", lambda: socket_engine)

    with TestClient(
        app,
        base_url="http://localhost:5173",
        backend_options={"loop_factory": selector_loop},
    ) as client:
        client.cookies.set("connecthub_session", raw_token)
        with client.websocket_connect(
            f"/ws/rooms/{room_id}", headers={"origin": "http://localhost:5173"}
        ) as socket:
            ready = socket.receive_json()
            assert ready["type"] == "connection.ready"
            presence = socket.receive_json()
            assert presence["type"] == "presence.changed"
            client_id = str(uuid.uuid4())
            socket.send_json(
                {
                    "type": "message.send",
                    "room_id": str(room_id),
                    "client_id": client_id,
                    "content": "Persist before broadcast",
                }
            )
            created = socket.receive_json()
            assert created["type"] == "message.created"
            assert created["message"]["content"] == "Persist before broadcast"
            socket.send_json({"type": "ping", "nonce": "health"})
            assert socket.receive_json()["type"] == "pong"

    stored = await db_session.scalar(
        select(Message).where(Message.client_idempotency_key == uuid.UUID(client_id))
    )
    assert stored is not None
    await connection_manager.clear()
    await socket_engine.dispose()


async def test_websocket_rejects_untrusted_origin(
    db_session: AsyncSession, migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_token, room_id = await seed_socket_context(db_session)
    socket_engine = create_async_engine(migrated_database_url, pool_pre_ping=True)
    realtime_router = importlib.import_module("app.realtime.router")
    monkeypatch.setattr(realtime_router, "get_engine", lambda: socket_engine)

    with TestClient(
        app,
        base_url="http://localhost:5173",
        backend_options={"loop_factory": selector_loop},
    ) as client:
        client.cookies.set("connecthub_session", raw_token)
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                f"/ws/rooms/{room_id}", headers={"origin": "https://attacker.invalid"}
            ):
                pass
        assert error.value.code == 4403

    await socket_engine.dispose()


async def test_websocket_rejects_revoked_session_and_private_room_nonmember(
    db_session: AsyncSession, migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_token, _ = await seed_socket_context(db_session)
    session = await db_session.scalar(
        select(AuthSession).where(AuthSession.token_hash == session_token_digest(raw_token))
    )
    assert session is not None
    session.revoked_at = datetime.now(UTC)
    await db_session.commit()
    socket_engine = create_async_engine(migrated_database_url, pool_pre_ping=True)
    realtime_router = importlib.import_module("app.realtime.router")
    monkeypatch.setattr(realtime_router, "get_engine", lambda: socket_engine)

    with TestClient(
        app,
        base_url="http://localhost:5173",
        backend_options={"loop_factory": selector_loop},
    ) as client:
        client.cookies.set("connecthub_session", raw_token)
        with pytest.raises(WebSocketDisconnect) as revoked:
            with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}):
                pass
        assert revoked.value.code == 4401

    active_token, _ = await seed_socket_context(db_session, "-active")
    private_room = Room(name="Other private room", description="", visibility="private")
    db_session.add(private_room)
    await db_session.commit()
    with TestClient(
        app,
        base_url="http://localhost:5173",
        backend_options={"loop_factory": selector_loop},
    ) as client:
        client.cookies.set("connecthub_session", active_token)
        with pytest.raises(WebSocketDisconnect) as hidden:
            with client.websocket_connect(
                f"/ws/rooms/{private_room.id}", headers={"origin": "http://localhost:5173"}
            ):
                pass
        assert hidden.value.code == 4404

    await socket_engine.dispose()


async def test_websocket_malformed_limit_and_frame_size_close_cleanly(
    db_session: AsyncSession, migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_token, room_id = await seed_socket_context(db_session)
    socket_engine = create_async_engine(migrated_database_url, pool_pre_ping=True)
    realtime_router = importlib.import_module("app.realtime.router")
    monkeypatch.setattr(realtime_router, "get_engine", lambda: socket_engine)

    with TestClient(
        app,
        base_url="http://localhost:5173",
        backend_options={"loop_factory": selector_loop},
    ) as client:
        client.cookies.set("connecthub_session", raw_token)
        with client.websocket_connect(
            f"/ws/rooms/{room_id}", headers={"origin": "http://localhost:5173"}
        ) as socket:
            socket.receive_json()
            socket.receive_json()
            for _ in range(3):
                socket.send_text("not-json")
                assert socket.receive_json()["error"]["code"] == "invalid_event"
            with pytest.raises(WebSocketDisconnect) as malformed:
                socket.receive_json()
            assert malformed.value.code == 1008

        with client.websocket_connect(
            f"/ws/rooms/{room_id}", headers={"origin": "http://localhost:5173"}
        ) as socket:
            socket.receive_json()
            socket.receive_json()
            socket.send_text("x" * 16_385)
            assert socket.receive_json()["error"]["code"] == "frame_too_large"
            with pytest.raises(WebSocketDisconnect) as oversized:
                socket.receive_json()
            assert oversized.value.code == 1009

    await socket_engine.dispose()
