import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Notification, Room, RoomInvitation, RoomMembership
from tests.integration.test_rooms_api import register_and_login

pytestmark = pytest.mark.integration


async def test_private_room_invitation_acceptance_and_isolation(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    alice_headers = await register_and_login(api_client, "alice", "alice@example.test")
    private = await api_client.post(
        "/api/v1/rooms",
        headers=alice_headers,
        json={"name": "Secret", "description": "Private", "visibility": "private"},
    )
    room_id = private.json()["room"]["id"]
    alice_cookies = dict(api_client.cookies)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:5173"
    ) as bob:
        bob_headers = await register_and_login(bob, "bob", "bob@example.test")
        discovery = await bob.get("/api/v1/rooms")
        hidden = await bob.get(f"/api/v1/rooms/{room_id}")
        direct_join = await bob.post(f"/api/v1/rooms/{room_id}/membership", headers=bob_headers)
        assert discovery.json()["items"] == []
        assert hidden.status_code == direct_join.status_code == 404

        api_client.cookies.clear()
        for name, value in alice_cookies.items():
            api_client.cookies.set(name, value)
        invited = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            headers=alice_headers,
            json={"username": "bob"},
        )
        duplicate = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            headers=alice_headers,
            json={"username": "bob"},
        )
        assert invited.status_code == 201
        assert duplicate.status_code == 409

        pending = await bob.get("/api/v1/users/me/invitations")
        invitation_id = pending.json()["items"][0]["id"]
        accepted = await bob.post(
            f"/api/v1/invitations/{invitation_id}/accept", headers=bob_headers
        )
        repeated = await bob.post(
            f"/api/v1/invitations/{invitation_id}/accept", headers=bob_headers
        )
        assert accepted.status_code == 200
        assert repeated.status_code == 409
        assert (await bob.get(f"/api/v1/rooms/{room_id}")).status_code == 200

    assert await db_session.scalar(select(Room).where(Room.id == uuid.UUID(room_id))) is not None
    assert await db_session.scalar(select(RoomInvitation.status)) == "accepted"
    assert len((await db_session.scalars(select(RoomMembership))).all()) == 2
    assert await db_session.scalar(select(Notification.type)) == "room_invitation"


async def test_invitation_decline_revoke_and_member_removal_notifications(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    alice_headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_id = (
        await api_client.post(
            "/api/v1/rooms",
            headers=alice_headers,
            json={"name": "Private", "visibility": "private"},
        )
    ).json()["room"]["id"]
    alice_cookies = dict(api_client.cookies)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:5173"
    ) as bob:
        bob_headers = await register_and_login(bob, "bob", "bob@example.test")
        api_client.cookies.clear()
        for name, value in alice_cookies.items():
            api_client.cookies.set(name, value)
        first = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            headers=alice_headers,
            json={"username": "bob"},
        )
        first_id = first.json()["invitation"]["id"]
        assert (
            await api_client.delete(
                f"/api/v1/rooms/{room_id}/invitations/{first_id}", headers=alice_headers
            )
        ).status_code == 200
        second = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            headers=alice_headers,
            json={"username": "bob"},
        )
        second_id = second.json()["invitation"]["id"]
        assert (
            await bob.post(f"/api/v1/invitations/{second_id}/decline", headers=bob_headers)
        ).status_code == 200
        third = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            headers=alice_headers,
            json={"username": "bob"},
        )
        third_id = third.json()["invitation"]["id"]
        await bob.post(f"/api/v1/invitations/{third_id}/accept", headers=bob_headers)
        members = await bob.get(f"/api/v1/rooms/{room_id}/members")
        assert members.status_code == 200
        bob_id = next(
            item["user_id"] for item in members.json()["items"] if item["username"] == "bob"
        )
        removed = await api_client.delete(
            f"/api/v1/rooms/{room_id}/members/{bob_id}", headers=alice_headers
        )
        assert removed.status_code == 204
        assert (await bob.get(f"/api/v1/rooms/{room_id}")).status_code == 404

    types = set((await db_session.scalars(select(Notification.type))).all())
    assert {"room_invitation", "room_membership_removed"}.issubset(types)


async def test_notification_ownership_pagination_and_read_operations(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    alice_headers = await register_and_login(api_client, "alice", "alice@example.test")
    room_id = (
        await api_client.post(
            "/api/v1/rooms",
            headers=alice_headers,
            json={"name": "Private", "visibility": "private"},
        )
    ).json()["room"]["id"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:5173"
    ) as bob:
        bob_headers = await register_and_login(bob, "bob", "bob@example.test")
        await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            headers=alice_headers,
            json={"username": "bob"},
        )
        listing = await bob.get("/api/v1/notifications", params={"limit": 1})
        item = listing.json()["items"][0]
        assert (await bob.get("/api/v1/notifications/unread-count")).json()["count"] == 1
        assert (
            await api_client.post(f"/api/v1/notifications/{item['id']}/read", headers=alice_headers)
        ).status_code == 404
        assert (
            await bob.post(f"/api/v1/notifications/{item['id']}/read", headers=bob_headers)
        ).status_code == 200
        assert (await bob.get("/api/v1/notifications/unread-count")).json()["count"] == 0
        assert (
            await bob.post("/api/v1/notifications/read-all", headers=bob_headers)
        ).status_code == 200

    assert await db_session.scalar(select(Notification.read_at)) is not None


async def test_owner_lists_sent_invitations_with_stable_status_and_authorization(
    api_client: AsyncClient,
) -> None:
    owner_headers = await register_and_login(api_client, "owner-list", "owner-list@example.test")
    room_id = (
        await api_client.post(
            "/api/v1/rooms",
            headers=owner_headers,
            json={"name": "Invitation history", "visibility": "private"},
        )
    ).json()["room"]["id"]

    async with (
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost:5173"
        ) as member_client,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost:5173"
        ) as invitee_a_client,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost:5173"
        ) as invitee_b_client,
    ):
        await register_and_login(member_client, "member-list", "member-list@example.test")
        invitee_a_headers = await register_and_login(
            invitee_a_client, "invite-a", "invite-a@example.test"
        )
        await register_and_login(invitee_b_client, "invite-b", "invite-b@example.test")
        first = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            json={"username": "invite-a"},
            headers=owner_headers,
        )
        second = await api_client.post(
            f"/api/v1/rooms/{room_id}/invitations",
            json={"username": "invite-b"},
            headers=owner_headers,
        )
        assert first.status_code == second.status_code == 201
        accepted = await invitee_a_client.post(
            f"/api/v1/invitations/{first.json()['invitation']['id']}/accept",
            headers=invitee_a_headers,
        )
        assert accepted.status_code == 200

        page_one = await api_client.get(f"/api/v1/rooms/{room_id}/invitations?limit=1")
        assert page_one.status_code == 200
        assert len(page_one.json()["items"]) == 1
        assert page_one.json()["next_cursor"]
        page_two = await api_client.get(
            f"/api/v1/rooms/{room_id}/invitations",
            params={"limit": 1, "cursor": page_one.json()["next_cursor"]},
        )
        statuses = {page_one.json()["items"][0]["status"], page_two.json()["items"][0]["status"]}
        assert statuses == {"pending", "accepted"}

        denied = await member_client.get(f"/api/v1/rooms/{room_id}/invitations")
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "room_owner_required"
