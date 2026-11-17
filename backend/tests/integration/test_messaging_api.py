import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import EmbeddingJob, Message, RoomMembership, User
from tests.integration.test_rooms_api import create_api_room, register_and_login

pytestmark = pytest.mark.integration


async def test_message_send_idempotency_history_search_and_sender_authority(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_id = (await create_api_room(api_client, headers)).json()["room"]["id"]
    client_id = str(uuid.uuid4())
    payload = {"client_id": client_id, "content": "  Hello 100% Python  "}
    first = await api_client.post(
        f"/api/v1/rooms/{room_id}/messages", headers=headers, json=payload
    )
    replay = await api_client.post(
        f"/api/v1/rooms/{room_id}/messages", headers=headers, json=payload
    )
    conflict = await api_client.post(
        f"/api/v1/rooms/{room_id}/messages",
        headers=headers,
        json={"client_id": client_id, "content": "Different"},
    )
    forged = await api_client.post(
        f"/api/v1/rooms/{room_id}/messages",
        headers=headers,
        json={"client_id": str(uuid.uuid4()), "content": "No", "sender_id": str(uuid.uuid4())},
    )

    assert first.status_code == replay.status_code == 201
    assert first.json()["message"]["id"] == replay.json()["message"]["id"]
    assert first.json()["message"]["content"] == "Hello 100% Python"
    assert replay.json()["idempotent_replay"] is True
    assert conflict.status_code == 409
    assert forged.status_code == 422
    assert await db_session.scalar(select(Message.content)) == "Hello 100% Python"
    assert await db_session.scalar(select(EmbeddingJob.status)) is None

    history = await api_client.get(f"/api/v1/rooms/{room_id}/messages")
    exact = await api_client.get(f"/api/v1/rooms/{room_id}/messages/search", params={"q": "%"})
    assert history.status_code == exact.status_code == 200
    assert len(history.json()["items"]) == 1
    assert len(exact.json()["items"]) == 1


@pytest.mark.parametrize("content", ["", " ", "x" * 4001])
async def test_message_validation(api_client: AsyncClient, content: str) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_id = (await create_api_room(api_client, headers)).json()["room"]["id"]
    response = await api_client.post(
        f"/api/v1/rooms/{room_id}/messages",
        headers=headers,
        json={"client_id": str(uuid.uuid4()), "content": content},
    )
    assert response.status_code == 422


async def test_message_history_cursor_ties_and_membership_authorization(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_id = (await create_api_room(api_client, headers)).json()["room"]["id"]
    user = await db_session.scalar(select(User).where(User.username == "alice"))
    assert user is not None
    tied = datetime(2026, 11, 16, tzinfo=UTC)
    ids = sorted([uuid.uuid4(), uuid.uuid4(), uuid.uuid4()], reverse=True)
    db_session.add_all(
        [
            Message(
                id=message_id,
                room_id=uuid.UUID(room_id),
                sender_id=user.id,
                content=f"message {index}",
                created_at=tied,
            )
            for index, message_id in enumerate(ids)
        ]
    )
    await db_session.commit()
    first = await api_client.get(f"/api/v1/rooms/{room_id}/messages", params={"limit": 2})
    second = await api_client.get(
        f"/api/v1/rooms/{room_id}/messages",
        params={"limit": 2, "before": first.json()["next_cursor"]},
    )
    assert [item["id"] for item in first.json()["items"]] == [str(value) for value in ids[:2]]
    assert [item["id"] for item in second.json()["items"]] == [str(ids[2])]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:5173"
    ) as bob:
        await register_and_login(bob, "bob", "bob@example.test")
        denied = await bob.get(f"/api/v1/rooms/{room_id}/messages")
        assert denied.status_code == 403


async def test_read_position_is_room_scoped_and_monotonic(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await register_and_login(api_client, "alice", "alice@example.test")
    first_room = (await create_api_room(api_client, headers, "One")).json()["room"]["id"]
    second_room = (await create_api_room(api_client, headers, "Two")).json()["room"]["id"]
    first_message = (
        await api_client.post(
            f"/api/v1/rooms/{first_room}/messages",
            headers=headers,
            json={"client_id": str(uuid.uuid4()), "content": "First"},
        )
    ).json()["message"]
    second_message = (
        await api_client.post(
            f"/api/v1/rooms/{first_room}/messages",
            headers=headers,
            json={"client_id": str(uuid.uuid4()), "content": "Second"},
        )
    ).json()["message"]
    wrong_room_message = (
        await api_client.post(
            f"/api/v1/rooms/{second_room}/messages",
            headers=headers,
            json={"client_id": str(uuid.uuid4()), "content": "Elsewhere"},
        )
    ).json()["message"]

    latest = await api_client.put(
        f"/api/v1/rooms/{first_room}/read-position",
        headers=headers,
        json={"message_id": second_message["id"]},
    )
    backwards = await api_client.put(
        f"/api/v1/rooms/{first_room}/read-position",
        headers=headers,
        json={"message_id": first_message["id"]},
    )
    wrong_room = await api_client.put(
        f"/api/v1/rooms/{first_room}/read-position",
        headers=headers,
        json={"message_id": wrong_room_message["id"]},
    )
    assert latest.status_code == 200
    assert backwards.status_code == 409
    assert wrong_room.status_code == 400
    membership = await db_session.scalar(
        select(RoomMembership).where(RoomMembership.room_id == uuid.UUID(first_room))
    )
    assert membership is not None
    assert str(membership.last_read_message_id) == second_message["id"]
